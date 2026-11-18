# s3 · A Unix shell in C

`s3` is a Unix shell written in C for a paired Software Systems assignment at Imperial College London. The current build runs foreground programs, waits for them to finish and supports `<`, `>` and `>>` for a single command.

## My contributions

I specified the acceptance checks for directory changes. One check enters two directories, attempts a missing one, then runs `cd -` twice. Comparing the prompt with `/bin/pwd` at each step catches a misleading prompt and a failed change that overwrites the previous directory. A relative output file gives a third check on the directory inherited by the next child process.

The [Task 3 verification record](https://github.com/Kage347/SS-A1-group-23/blob/a5ac9b399ea4dfa0796192108cb034f83abae53e/docs/task-3-checks.md) contains the commands and observed results. At the tested revision, `cd A` appeared to succeed on macOS, but the next `/bin/pwd` still reported the starting directory. The `cd` built-in is pending. AI assistance was used to execute tests and prepare the documentation.

## Build and try it

From the repository root on macOS or Linux with a C compiler, run the following commands. The temporary directory keeps the example files together. This session was verified on macOS.

```sh
demo=$(mktemp -d)
cc -std=c11 s3main.c s3.c -o "$demo/s3"
(cd "$demo" && ./s3)
```

```console
[s3]$ echo alpha > words.txt
[s3]$ echo beta >> words.txt
[s3]$ tr a-z A-Z < words.txt
ALPHA
BETA
[s3]$ exit
```

## Project credits

Sarim Baig supplied the [assignment and starter code](https://sarimbaig01.github.io/elec50014/Docs/Assignment1.html#p1). Hanns Lim implemented [foreground command execution and `exit`](https://github.com/HannsL2/SS-A1-group-23/commit/5bcd6101233b605a843f4aefadb777304f65d692) and [file redirection](https://github.com/HannsL2/SS-A1-group-23/commit/5caf45f4db22727152ff443a6cd8f7b3d04ed9e6). In the redirection path, the child opens the file and directs its own input or output to it before calling `execvp`. The parent can still print the next prompt to the terminal.
