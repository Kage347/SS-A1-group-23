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

///With inline functions, the compiler replaces the function call 
///with the actual function code;
///inline improves speed and readability; meant for short functions (a few lines).
///the static here avoids linker errors from multiple definitions (needed with inline).
static inline void reap(void)
{
    wait(NULL);
}

///Shell I/O and related functions (add more as appropriate)
void read_command_line(char line[]);
void construct_shell_prompt(void);
int open_current_directory(void);
void run_cd(char *args[], int argsc, int *previous_fd);
void parse_command(char line[], char *args[], int *argsc);

///Child functions (add more as appropriate)
void child(char *args[], int argsc);

///Program launching functions (add more as appropriate)
void launch_program(char *args[], int argsc);
void launch_program_with_redirection(char *args[], int argsc);
bool command_with_redirection(char line[]);
int find_redirection_operator(char *args[], int argsc);
void child_with_output_redirected(char *args[], int argsc, int op_index);
void child_with_input_redirected(char *args[], int argsc, int op_index);
#endif
