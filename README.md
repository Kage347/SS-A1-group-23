# s3 · Commands with pipes

`s3` is a Unix shell written in C for a paired Software Systems assignment at Imperial College London. This personal branch contains an AI-written study reference for Task 4, built on the signed-off Task 3 reference. The lecturer supplied the starter shell and pipe examples. Hanns Lim implemented the original foreground commands and file redirection. [Assignment §4](https://sarimbaig01.github.io/elec50014/Docs/Assignment1.html#p4) · [Lecture 3 pipe example](https://github.com/sarimbaig01/ss/blob/b1532618d3c05c1514c78913472e6393ad98e409/class_codes/lec3/pipe2.c) · [Hanns’s implementation](https://github.com/Kage347/SS-A1-group-23/commit/5caf45f4db22727152ff443a6cd8f7b3d04ed9e6) · [Task 3 reference](https://github.com/Kage347/SS-A1-group-23/tree/86d0489eefad87d026aa8016f7866357fa4e5757)

## Build and try it

From this checkout, run the following in your usual shell on macOS or Linux.

```sh
cc -std=c11 -Wall -Wextra -Wpedantic -Werror s3main.c s3.c -o s3
binary="$PWD/s3"
demo=$(mktemp -d)
mkdir "$demo/txt"
printf '%s\n' 'burning coal' 'cold rain' 'burning field' 'burning ash' > "$demo/txt/phrases.txt"
(cd "$demo" && LC_ALL=C "$binary")
```

Enter these commands at the `s3` prompt.

```sh
cat txt/phrases.txt | sort > txt/phrases_sorted.txt
cat txt/phrases_sorted.txt
tr a-z A-Z < txt/phrases.txt | grep BURN | sort | wc -l
exit
```

The first command creates the output file. The second prints `burning ash`, `burning coal`, `burning field` and `cold rain` on separate lines. The four-stage pipeline prints `3`.

## Why every stage starts before the shell waits

A pipe has a finite buffer. A small producer can write its entire output and exit before its consumer starts. A larger producer fills the buffer and blocks in `write`. If the parent were waiting for the producer to exit, it would never start the consumer that could drain the buffer. In `launch_pipeline`, the shell starts every stage before calling `wait_for_stages`. The parent closes each write end after the producing child forks and keeps the read end only until the next child forks. Once the last writer closes, the consumer can read EOF. [Pipeline launcher](s3main.c) · [Child execution and redirection](s3.c)

Each stage can use one file redirection. The child connects its pipes first and then applies `<`, `>` or `>>`. For example, in `cat input | sort > saved | wc -l`, `sort` writes to `saved` and `wc` reads EOF and prints zero. Standalone `cd` changes the shell’s directory. Inside a pipeline, `cd` and `exit` affect only their stage.

## Verify

Run these from the checkout as an ordinary user. The tests use temporary fixtures. The pipeline suite puts a deadline on commands that would hang if a pipe end leaked or the parent waited too early.

```sh
python3 -B tests/task4_pipes.py ./s3
python3 -B tests/task3_reference.py ./s3
python3 -B tests/task3_deep.py ./s3
python3 -B tests/task3_permissions.py ./s3
```

The inherited input buffer is 1,024 bytes and each stage allows 127 tokens including its command. Pipeline length is bounded by that input and available system resources. Separate a redirection operator and its filename with whitespace. Quoting, escaping, sequential batches and job control are outside this reference.
