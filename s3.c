#include "s3.h"

void construct_shell_prompt(void)
{
    // On macOS, getcwd allocates enough space for the full physical path.
    char *cwd = getcwd(NULL, 0);
    if (cwd != NULL) {
        printf("[%s s3]$ ", cwd);
        free(cwd);
    } else {
        fputs("[? s3]$ ", stdout);
    }
    fflush(stdout);
}

int open_current_directory(void)
{
#ifdef O_SEARCH
    return open(".", O_SEARCH | O_DIRECTORY | O_CLOEXEC);
#else
    return open(".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
#endif
}

void run_cd(char *args[], int argsc, int *previous_fd)
{
    if (argsc > 2) {
        fputs("cd: too many arguments\n", stderr);
        return;
    }
    const char *target = args[ARG_1];
    bool use_previous = target != NULL && strcmp(target, "-") == 0;
    if (target == NULL) {
        target = getenv("HOME");
        if (target == NULL || target[0] == '\0') {
            fputs("cd: HOME is unset or empty\n", stderr);
            return;
        }
    } else if (use_previous && *previous_fd < 0) {
        fputs("cd: previous directory unavailable\n", stderr);
        return;
    }

    int departing_fd = open_current_directory();
    int result = use_previous ? fchdir(*previous_fd) : chdir(target);
    if (result == -1) {
        perror("cd");
        if (departing_fd >= 0) {
            close(departing_fd);
        }
        return;
    }

    // If opening the directory we left failed, -1 clears the older history.
    if (*previous_fd >= 0) {
        close(*previous_fd);
    }
    *previous_fd = departing_fd;
}

void read_command_line(char line[])
{
    construct_shell_prompt();

    ///See man page of fgets(...)
    if (fgets(line, MAX_LINE, stdin) == NULL)
    {
        if (feof(stdin)) {
            exit(EXIT_SUCCESS);
        }
        perror("fgets failed");
        exit(1);
    }
    line[strcspn(line, "\n")] = '\0';
}

// Argument pointers refer to the stage's portion of the input line.
bool parse_stage(char *text, Stage *stage, bool standalone)
{
    bool has_redirection = strpbrk(text, "<>") != NULL;
    stage->argsc = 0;
    stage->redirect_index = -1;
    char *word = strtok(text, " \t");
    while (word != NULL && stage->argsc < MAX_ARGS - 1) {
        stage->args[stage->argsc++] = word;
        word = strtok(NULL, " \t");
    }
    stage->args[stage->argsc] = NULL;

    if (stage->argsc == 0) {
        if (!standalone) {
            fputs("s3: syntax error: empty pipeline stage\n", stderr);
        }
        return standalone;  // An empty command line just prints another prompt.
    }

    const char *name = stage->args[0];
    if (strcmp(name, "cd") == 0) {
        stage->kind = BUILTIN_CD;
    } else if (strcmp(name, "exit") == 0) {
        stage->kind = BUILTIN_EXIT;
    } else {
        stage->kind = EXTERNAL_COMMAND;
    }

    // Standalone built-ins receive their original arguments, as in Task 3.
    if (!has_redirection || (standalone && stage->kind != EXTERNAL_COMMAND)) {
        return true;
    }
    for (int i = 0; i < stage->argsc; i++) {
        const char *arg = stage->args[i];
        if (strcmp(arg, "<") == 0 || strcmp(arg, ">") == 0 || strcmp(arg, ">>") == 0) {
            if (i == 0 || i + 1 == stage->argsc) {
                break;
            }
            stage->redirect_index = i;
            return true;
        }
    }
    fputs("s3: syntax error near redirection symbol\n", stderr);
    return false;
}

// The caller transfers ownership of fd, even when dup2 fails.
void connect_stream(int fd, int stream)
{
    if (fd == stream) {
        return;
    }
    if (dup2(fd, stream) < 0) {
        perror("dup2");
        _exit(1);
    }
    close(fd);
}

static void redirect_stage(Stage *stage)
{
    int index = stage->redirect_index;
    const char *op = stage->args[index];
    int stream = STDIN_FILENO;
    int flags = O_RDONLY;
    if (strcmp(op, "<") != 0) {
        stream = STDOUT_FILENO;
        flags = O_WRONLY | O_CREAT;
        flags |= strcmp(op, ">>") == 0 ? O_APPEND : O_TRUNC;
    }
    int fd = open(stage->args[index + 1], flags, 0644);
    if (fd < 0) {
        perror("open");
        _exit(1);
    }
    connect_stream(fd, stream);
    stage->args[index] = NULL;
    stage->argsc = index;
}

_Noreturn void execute_child(Stage *stage, int previous_fd)
{
    // File redirection overrides the pipe connection for that stream.
    if (stage->redirect_index >= 0) {
        redirect_stage(stage);
    }
    if (stage->kind == BUILTIN_CD) {
        run_cd(stage->args, stage->argsc, &previous_fd);
        _exit(0);
    }
    if (stage->kind == BUILTIN_EXIT) {
        _exit(0);
    }
    execvp(stage->args[0], stage->args);
    fprintf(stderr, "s3: execvp %s: %s\n", stage->args[0], strerror(errno));
    _exit(1);
}
