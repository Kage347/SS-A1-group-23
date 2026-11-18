#ifndef _S3_H_
#define _S3_H_

#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif

///See reference for what these libraries provide
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdbool.h>
#include <errno.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>

///Constants for array sizes, defined for clarity and code readability
#define MAX_LINE 1024
#define MAX_ARGS 128

///Enum for readable argument indices (use where required)
enum ArgIndex
{
    ARG_PROGNAME,
    ARG_1,
    ARG_2,
    ARG_3,
};

typedef struct {
    char *args[MAX_ARGS];
    int argsc;
    enum { EXTERNAL_COMMAND, BUILTIN_CD, BUILTIN_EXIT } kind;
    int redirect_index;
    pid_t pid;
} Stage;

void read_command_line(char line[]);
void construct_shell_prompt(void);
int open_current_directory(void);
void run_cd(char *args[], int argsc, int *previous_fd);
bool parse_stage(char *text, Stage *stage, bool standalone);
void connect_stream(int fd, int stream);
_Noreturn void execute_child(Stage *stage, int previous_fd);

#endif
