#include "s3.h"

void construct_shell_prompt(void)
{
    char cwd[PATH_MAX];
    if (getcwd(cwd, sizeof cwd) != NULL) {
        printf("[%s s3]$ ", cwd);
    } else {
        fputs("[? s3]$ ", stdout);
    }
    fflush(stdout);
}

void run_cd(char *args[], int argsc, char previous[PATH_MAX])
{
    const char *target;
    if (argsc > 2) {
        fputs("cd: too many arguments\n", stderr);
        return;
    }
    if (argsc == 1) {
        target = getenv("HOME");
        if (target == NULL || target[0] == '\0') {
            fputs("cd: HOME is unset or empty\n", stderr);
            return;
        }
    } else if (strcmp(args[ARG_1], "-") == 0) {
        if (previous[0] == '\0') {
            fputs("cd: previous directory unavailable\n", stderr);
            return;
        }
        target = previous;
    } else {
        target = args[ARG_1];
    }

    char departing[PATH_MAX];
    if (getcwd(departing, sizeof departing) == NULL) {
        // A removed directory can still be left, but has no path to remember.
        departing[0] = '\0';
    }
    if (chdir(target) == -1) {
        perror("cd");
        return;
    }
    // Only a successful move changes where the next cd - should go.
    strcpy(previous, departing);
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

void parse_command(char line[], char *args[], int *argsc)
{
    ///Implements simple tokenization (space delimited)
    ///Note: strtok puts '\0' (null) characters within the existing storage, 
    ///to split it into logical cstrings.
    ///There is no dynamic allocation.

    ///See the man page of strtok(...)
    char *token = strtok(line, " ");
    *argsc = 0;
    while (token != NULL && *argsc < MAX_ARGS - 1)
    {
        args[(*argsc)++] = token;
        token = strtok(NULL, " ");
    }
    
    args[*argsc] = NULL; ///args must be null terminated
}

///Launch related functions
void child(char *args[], int argsc)
{
    (void)argsc;  // execvp reads args up to its terminating null pointer.
    execvp(args[ARG_PROGNAME], args);
    perror("execvp");
}

void launch_program(char *args[], int argsc)
{
    if (argsc == 0) {
        return;
    }
    if (strcmp(args[ARG_PROGNAME], "exit") == 0) {
        exit(0);
    }
    pid_t pid = fork();

    if (pid == 0) {
        child(args, argsc);
        exit(1);
    }
    else if (pid < 0){
        perror("fork");
    }
}

void launch_program_with_redirection(char *args[], int argsc) {
    if (argsc == 0) {
        return;
    }
    if (strcmp(args[ARG_PROGNAME], "exit") == 0) {
        exit(0);
    }

    int op_index = find_redirection_operator(args, argsc);
    if (op_index == -1 || op_index + 1 >= argsc) {
        fprintf(stderr, "s3: syntax error near redirection symbol\n");
        return;
    }

    pid_t pid = fork();

    if (pid == 0) {
        if (strcmp(args[op_index], "<") == 0) {
            child_with_input_redirected(args, argsc, op_index);
        }
        else {
            child_with_output_redirected(args, argsc, op_index);
        }
        exit(1);
    }
    else if (pid < 0){
        perror("fork");
    }
}

bool command_with_redirection(char line[]){
    return strchr(line, '<') != NULL || strchr(line, '>') != NULL;
}

int find_redirection_operator(char *args[], int argsc) {
    for (int i = 0; i < argsc; i++) {
        if (strcmp(args[i], "<") == 0 || strcmp(args[i], ">>") == 0 || strcmp(args[i], ">") == 0) {
            return i;
        }
    }
    return -1;
}

void child_with_output_redirected(char *args[], int argsc, int op_index) {
    int flags;
    if (strcmp(args[op_index], ">>") == 0){
        flags = O_WRONLY | O_CREAT | O_APPEND;
    }
    else {
        flags = O_WRONLY | O_CREAT | O_TRUNC;
    }

    int fd = open(args[op_index + 1], flags, 0644);
    if (fd < 0) {
        perror("open");
        exit(1);
    }

    dup2(fd, STDOUT_FILENO);
    close(fd);

    args[op_index] = NULL;
    child(args, argsc);
}

void child_with_input_redirected(char *args[], int argsc, int op_index) {
    int flags = O_RDONLY;

    int fd = open(args[op_index + 1], flags);
    if (fd < 0) {
        perror("open");
        exit(1);
    }   

    dup2(fd, STDIN_FILENO);
    close(fd);

    args[op_index] = NULL;
    child(args, argsc);
}
