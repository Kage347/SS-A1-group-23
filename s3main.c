#include "s3.h"

static bool parse_pipeline(char *line, Stage stages[], size_t count)
{
    for (size_t i = 0; i < count; i++) {
        char *separator = strchr(line, '|');
        if (separator != NULL) {
            *separator = '\0';
        }
        if (!parse_stage(line, &stages[i], count == 1)) {
            return false;
        }
        if (separator != NULL) {
            line = separator + 1;
        }
    }
    return true;
}

static void wait_for_stages(const Stage stages[], size_t started)
{
    for (size_t i = 0; i < started; i++) {
        pid_t result;
        do {
            result = waitpid(stages[i].pid, NULL, 0);
        } while (result == -1 && errno == EINTR);
        if (result == -1) {
            perror("waitpid");
        }
    }
}

static void launch_pipeline(Stage stages[], size_t count, int previous_fd)
{
    int input = -1;
    size_t started = 0;
    while (started < count) {
        int next[2] = {-1, -1};
        if (started + 1 < count && pipe(next) == -1) {
            perror("pipe");
            break;
        }

        pid_t pid = fork();
        if (pid == 0) {
            // An early reader exit should stop a writer even if s3 inherited SIGPIPE ignored.
            signal(SIGPIPE, SIG_DFL);
            if (input >= 0) {
                connect_stream(input, STDIN_FILENO);
            }
            if (next[0] >= 0) {
                close(next[0]);  // Only the following stage reads from this pipe.
                connect_stream(next[1], STDOUT_FILENO);
            }
            execute_child(&stages[started], previous_fd);
        }
        if (pid == -1) {
            perror("fork");
            if (next[0] >= 0) {
                close(next[0]);
                close(next[1]);
            }
            break;
        }

        stages[started].pid = pid;
        started++;
        if (input >= 0) {
            close(input);
        }
        if (next[1] >= 0) {
            close(next[1]);  // A parent-held writer would keep the next reader from EOF.
        }
        input = next[0];  // Retain just the read end needed for the next fork.
    }

    if (started < count) {
        if (input >= 0) {
            close(input);
        }
        // An incomplete pipeline can include a sleeping or blocked child.
        for (size_t i = 0; i < started; i++) {
            kill(stages[i].pid, SIGKILL);
        }
    }
    // Start all consumers before waiting: a producer can fill its pipe and block.
    wait_for_stages(stages, started);
}

static void run_line(char *line, int *previous_fd)
{
    size_t count = 1;
    for (const char *p = line; *p != '\0'; p++) {
        if (*p == '|') {
            count++;
        }
    }
    Stage *stages = calloc(count, sizeof *stages);
    if (stages == NULL) {
        perror("calloc");
        return;
    }
    if (parse_pipeline(line, stages, count) && stages[0].argsc > 0) {
        if (count == 1 && stages[0].kind == BUILTIN_EXIT) {
            free(stages);
            exit(0);
        }
        if (count == 1 && stages[0].kind == BUILTIN_CD) {
            run_cd(stages[0].args, stages[0].argsc, previous_fd);
        } else {
            launch_pipeline(stages, count, *previous_fd);
        }
    }
    free(stages);
}

int main(void)
{
    char line[MAX_LINE];
    int previous_fd = open_current_directory();
    // Keep foreground children waitable even if the launching process ignored SIGCHLD.
    signal(SIGCHLD, SIG_DFL);
    while (1) {
        read_command_line(line);
        run_line(line, &previous_fd);
    }
}
