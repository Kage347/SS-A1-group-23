#include "s3.h"

int main(void)
{

    ///Stores the command line input
    char line[MAX_LINE];

    ///Stores pointers to command arguments.
    ///The first element of the array is the command name.
    char *args[MAX_ARGS];

    ///Stores the number of arguments
    int argsc;

    int previous_fd = open_current_directory();

    while (1) {
        read_command_line(line);

        int redirection = command_with_redirection(line);

        parse_command(line, args, &argsc);

        if (argsc > 0 && strcmp(args[ARG_PROGNAME], "cd") == 0) {
            // cd changes this shell's directory and creates no child to reap.
            run_cd(args, argsc, &previous_fd);
            continue;
        }

        if (redirection){
            launch_program_with_redirection(args, argsc); 
        }
        else {
            launch_program(args, argsc);
        }

        reap();
    }

    return 0;
    
}
