# s3 shell · Task 3 study reference

## Build and verify

From this branch on macOS, run:

```sh
cc -std=c11 -Wall -Wextra -Wpedantic s3main.c s3.c -o s3
python3 tests/task3_reference.py ./s3
./s3
```

To try the feature interactively, start in the repository root. Run `cd docs`, then `/bin/pwd`. The prompt and the command should both show the repository’s `docs` directory. Run `cd -` to return to the repository root. Bare `cd` takes you to the directory in `HOME`.

## Trace a directory change

1. In `s3main.c`, `main` remembers the startup directory. It recognises the exact command name `cd` after tokenisation and runs the built-in in the shell process. There is no child to wait for. The next external command inherits the location selected by this shell.
2. In `s3.c`, `run_cd` selects the explicit path, the value of `HOME`, or the remembered directory. It saves the path it is leaving and calls `chdir`. Only a successful call updates the remembered path. If you move from A to B, fail to enter a missing directory, and run `cd -` twice, you visit A and then B.
3. Before the next input, `construct_shell_prompt` calls `getcwd` and prints the current physical directory. The first `cd -` can stay in the startup directory. If the shell cannot resolve its current directory, the prompt shows `?`. It can still leave an unlinked directory using an absolute path.
4. A redirected external command still uses Hanns’s child process path. After a successful `cd`, a relative output filename resolves in the new directory. The child's `dup2` sends its output to that file while the shell retains its terminal output.

## Scope

This reference implements standalone `cd` with named, relative and absolute paths, `.`, `..`, home and previous-directory handling. Extra arguments and unset or empty `HOME` produce a diagnostic. It uses the starter’s space-separated command syntax. Paths containing spaces, shell quoting, redirection on the built-in itself, pipelines and sequential batches fall outside this reference. Directory storage uses the platform’s `PATH_MAX` limit.
