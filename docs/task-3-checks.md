# Task 3 acceptance checks

The published C sources at [5caf45f](https://github.com/HannsL2/SS-A1-group-23/commit/5caf45f4db22727152ff443a6cd8f7b3d04ed9e6) implement external commands, `exit` and single-stream redirection. This branch records the starting results for the paired shell assignment. Ahsan specified the directory-history and redirection scenarios. AI assistance was used to run the checks and document the observations.

## Reproduce in a terminal

From the repository root, build into a temporary directory. The physical path avoids the `/tmp` symlink on macOS. Only the test shell gets the temporary home directory.

```sh
trial=$(mktemp -d /tmp/s3-cd.XXXXXX)
trial=$(cd "$trial" && pwd -P)
mkdir -p "$trial/A/B" "$trial/home"
cc -std=c11 s3main.c s3.c -o "$trial/s3"
(cd "$trial" && env -u OLDPWD HOME="$trial/home" PATH=/usr/bin:/bin ./s3)
```

Enter these lines in the same `s3` session. For each `/bin/pwd`, compare the printed path with the next prompt. A prompt format can differ from the lecturer’s example as long as it identifies the actual working directory.

```text
/bin/pwd
cd -
/bin/pwd
cd A
/bin/pwd
cd B
/bin/pwd
cd missing
/bin/pwd
cd -
/bin/pwd
cd -
/bin/pwd
/bin/echo moved > result.txt
cd .
/bin/pwd
cd ..
/bin/pwd
cd /
/bin/pwd
cd
/bin/pwd
exit
```

Back in the original terminal, inspect both the location and the contents of the output file.

```sh
find "$trial" -name result.txt -print -exec cat {} \;
```

## Expected and observed

`START` means the physical path printed by the first `/bin/pwd`. The observed column comes from a macOS pseudo-terminal session with a fresh fixture. Every observed prompt was `[s3]$ `.

| Input | Expected Task 3 behaviour | Observed at `5caf45f` |
| --- | --- | --- |
| Startup, `/bin/pwd` | Prompt contains `START` and agrees with `pwd`. | `pwd` printed `START`. Prompt omitted it. |
| First `cd -` | With the lecturer’s history initialization, stay at `START` without an error. | Stayed at `START`. The macOS `cd` utility reported `OLDPWD not set`. |
| `cd A`, then `cd B` | `START/A`, then `START/A/B`. | Both `pwd` calls returned `START`. `cd A` gave no error. `cd B` could not find `B` there. |
| `cd missing`, then `cd -` twice | Error, stay in `A/B`, return to `A`, then back to `A/B`. Each prompt follows `pwd`. | Error, then `START` three times. Both `cd -` calls reported unset history. The shell never reached the precondition for testing history preservation. |
| `/bin/echo moved > result.txt` | Only `START/A/B/result.txt` exists, containing `moved` and a newline. | Only `START/result.txt` existed, with the correct bytes. |
| `cd .`, then `cd ..` | From `A/B`, stay there, then move to `A`. | Both printed `START`. A no-op alone cannot demonstrate support for `cd .`. |
| `cd /` | Prompt and `pwd` show `/`. | `pwd` still printed `START`. |
| `cd` | Prompt and `pwd` show `START/home`. | `pwd` still printed `START`. |

The same history sequence in `/bin/sh` reached `A`, `A/B`, `A/B`, `A`, `A/B`, and wrote `A/B/result.txt`. This independently checks the fixture and its expected paths. The first-use convention comes from the [lecturer’s scaffold](https://github.com/sarimbaig01/elec50014/blob/a49370602cf81884044fecf4d44c0c248de5cd25/c/s3main_3.c#L8-L11).

## Regression baseline

All 13 focused Task 1–2 checks passed, covering external commands and arguments, `exit`, blank input, recovery after an unknown command, and file creation, truncation, appending and input redirection. The ordinary build succeeded. Adding `-Wall -Wextra -Wpedantic` to the C11 build also succeeded with existing warnings about `reap()` having no prototype, unused parameters and missing final newlines.

Five existing input and I/O defects reproduced separately. EOF exits with status 1. A final line without a newline loses its last character. Oversized lines can become separate commands, and argument lists exceeding the fixed array are truncated. With piped input and output, a failed executable under `>` can flush a copy of the prompt into its output file.
