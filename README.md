# Plainly

A programming language written in plain English. No symbols, no brackets, no quote marks, no indentation rules. Programs read like instructions, and the compiler checks them before anything runs.

**Version 1.1.0.** Free to use. See `LICENSE`.

> **Status: first public release.** It is tested (see Testing below) but young, and it has not been security audited. Please do not rely on it for anything where safety matters.

```
define total price of items as a list of item giving a number
let sum be 0
for each item in items do
add price of item times quantity of item to sum
end for
give back sum
end define
```

## What it can do

- **Read like English.** Sentences such as `let total be 0`, `say the words Hello end words`, and `for each score in scores do`. Names can be several words, like `total price`.
- **Catch mistakes before running.** It checks types, so adding text to a number or promising a value a function never gives back is an error with a plain explanation.
- **Have no null.** A value that might be missing is a `maybe`, and you must handle both cases.
- **Control file access.** A program cannot read or write a file until it says `allow reading the file NAME` or `allow writing the file NAME`.
- **Run two ways.** `run` uses the full language. `native` compiles to a fast machine-code program through a C compiler.
- **Give friendly errors.** Messages name the line, show it, and suggest fixes such as "did you mean ...?".

## Install

**Option 1: no Python needed.** Download the app for your system from the Releases page (Windows, Mac or Linux), then:

```
plainly-Linux run hello.plain
```

**Option 2: with pip.** If you have Python 3:

```
pip install plainly-lang
plainly run hello.plain
```

**Option 3: just the file.** Download `plainly.py` and run `python3 plainly.py run hello.plain`.

The `native` command also needs a C compiler (gcc, cc or clang) on your machine.

## Full guide: how to use Plainly

### 1. Pick how you will run it

| You have | Do this |
|---|---|
| Nothing to install | Open the browser version (`plainly-web.html`), pick a lesson, press **Run** |
| Python 3 | Download `plainly.py`, then `python3 plainly.py run hello.plain` (Windows: `python` or `py`) |
| Python and pip | `pip install plainly-lang`, then `plainly run hello.plain` |
| Phone (Android) | Install Termux, then `pkg install python`, and use the Python line above |
| Google Colab | Upload the files, then `!python plainly.py run hello.plain` |

### 2. Write your first program

Make a text file called `hello.plain`:

```
note my first program
say the words Hello, world.
```

Run it: `python3 plainly.py run hello.plain`. It prints `Hello, world.`

### 3. The rules in one minute

1. **One sentence per line.**
2. **Comments:** a line starting with `note` is ignored.
3. **Text:** write `the words` then your text. It ends at the end of the line, at `end words`, or by itself before `followed by`, `joined to`, `that asks` and `and the words`. Text can hold any symbols.
4. **Blocks** (`if`, `while`, `repeat`, `for each`, `define`, `when`) are closed with `end` and the block name, such as `end if`.
5. **No symbols outside text:** no `_ : " ( ) [ ] { } ;`. Say it in words instead: `plus`, `minus`, `times`, `divided by`, `modulo`, `is greater than`.
6. **Names** can be up to 6 words, cannot start with a number, and cannot be `true` or `false`.
7. **Inputs take one value each.** Write `let smaller be n minus 1` and then `factorial of smaller`. Writing `factorial of n minus 1` means `(factorial of n) minus 1`.

### 4. Cheat sheet

| To do this | Write this |
|---|---|
| Show something | `say the words Hi` or `say total` |
| Make a value | `let age be 12` |
| Change it | `set age to 13`, `add 1 to age`, `subtract 2 from age` |
| Join text | `say the words Age is followed by age` |
| Choose | `if age is at least 18 then` ... `otherwise` ... `end if` |
| Repeat | `repeat 3 times do` ... `end repeat` |
| Loop while true | `while count is less than 5 do` ... `end while` |
| Loop over a list | `for each pet in pets do` ... `end for` |
| Make a list | `let pets be a list of the words cat and the words dog`, `an empty list of number` |
| Get an entry | `entry 1 of pets` (counting from 1) |
| Own command | `define double of n as number giving number` ... `give back n times 2` ... `end define` |
| Several inputs | `define add up of a as number with b as number giving number` and call `add up of 4 with 5` |
| Check text | `said contains the words hello end words` |
| Maybe a value | `parsed number of the words 42 end words`, then `has a value as x` or `or else 0` |

Types are `number`, `text`, `truth` (yes or no), `a list of ...`, `maybe ...`, and your own records.

### 5. Commands

| Command | What it does |
|---|---|
| `run FILE` | Check, then run |
| `check FILE` | Check only |
| `fix FILE` | Repair common mistakes into `FILE.fixed.plain` (never adds permissions) |
| `native FILE` | Compile to a fast native program (needs gcc, cc or clang) |
| `build FILE` / `c FILE` | Show the generated Python / C |
| `version` | Show the version |

### 6. Files, memory and permissions

A program must ask before it touches anything:

```
allow reading the file prices.txt
let prices be the numbers in the file prices.txt
allow writing the file report.txt
write the words Done end words to the file report.txt
allow remembering in the file memory.json
remember total as visits
```

Only files in the program's own folder can be used. If a permission is missing, Plainly stops before running and tells you exactly what to add.

### 7. Build a website (Python version)

```
when someone visits the path home do
show a heading with the words My site
show a box called name
show a paragraph called answer with the words Type a name.
show a button with the words Greet that asks the path hello and shows the reply in the paragraph called answer
reply with the page
end when
when someone visits the path hello do
reply with the words Hello followed by the visitor sent name
end when
start the server on port 8080
```

Run it, then open `http://127.0.0.1:8080`. The server answers only on your own computer. See `examples/app.plain`, `notes.plain` and `chatbot.plain`.

### 8. Fix problems

- **Plainly found a problem:** read the line it shows. In a terminal it offers to fix common ones; or run `fix FILE`.
- **I do not know what X means:** a name is misspelled or was never created with `let`.
- **Text swallowed the rest of the line:** close it with `end words`, especially before `then`, `to` or `contains`.
- **Has not asked permission yet:** add the `allow ...` line it names. This is on purpose.
- **Permission denied when running a native program:** build it in your home folder, not a download or temporary folder.
- **Port may already be in use:** change the number in `start the server on port ...`.
- **`python3` not found (Windows):** use `python` or `py`.

## Learn it in ten minutes

Start with the lessons in `examples/lessons` (lessons 1 to 6) or in the browser version (lessons 1 to 8, which also covers pages and a chatbot). Each lesson is a short program with `note` lines that explain it. Run it, change it, run it again.

## Bots

**What Plainly can do today:** chatbots that follow rules you write. `text contains the words hello end words` checks for words and ignores capital letters. In the browser version, Lesson 8 is a chatbot on a page. In the Python version, `examples/chatbot.plain` runs a chatbot on your own server, and a bot can remember things between visits.

**What it cannot do yet:** Discord, Telegram or WhatsApp bots, or bots that visit other websites. Those need to reach other services over the internet, hold secret keys, and keep live connections. Plainly programs deliberately cannot reach the internet, so a safe design would need a new permission, such as asking to talk to one named site, plus sending and receiving data. That is not built yet.

## Names and text

- **Names** can use any words, even ones like `end`, `from` or `the cat`. A name can be up to 6 words, cannot start with a number, and cannot be `true` or `false`.
- A name can match a built-in, like `length`. `length of items` still calls the built-in, and plain `length` is your value.
- **Text** starts with `the words` and can hold any symbols, such as `Total: (5) done; ok`. It ends at the end of the line, at `end words`, or by itself before `followed by` and `joined to`.

## Fixing mistakes automatically

```
python3 plainly.py fix program.plain
```

This writes `program.fixed.plain` and lists every change. Your original file is never touched. It repairs the mistakes people make most:

- Habits from other languages: `print`, `var`, `else`, `elif`, `return`, `endif`, quoted text, brackets and colons.
- Misspelled sentence starters (`sya` becomes `say`) and misspelled names (`totl` becomes `total`).
- A missing `then` or `do`, a missing `end`, or the wrong `end` for a block.

When you run a program that has a fixable problem in a terminal, Plainly offers to fix it and run it right away.
- Using `plus` to join text, which becomes `followed by`.

It never adds permissions. Whether a program may touch files or memory is your decision, so it stops and asks you instead. In the browser version, a **Fix it** button appears when a problem can be repaired.

## Testing

```
python3 tests/run_tests.py
node tests/web_test.js
```

The first checks the examples, errors, names, the fixer, memory, the server, and the generated C. The second checks the browser version.

## Quick start

You need Python 3. The `native` command also needs a C compiler (gcc, cc or clang).

```
python3 plainly.py run examples/hello.plain
python3 plainly.py check examples/shop.plain
python3 plainly.py native examples/speed.plain
```

| Command | What it does |
|---|---|
| `run FILE` | Check, then run the program |
| `check FILE` | Check only |
| `native FILE` | Check, then build a fast native program |
| `build FILE` | Show the generated Python |
| `c FILE` | Show the generated C |

On Windows the command is often `python` or `py`. Runs fine in Google Colab, Replit, Codespaces, PythonAnywhere and Termux.

## Websites: backend and frontend

**Backend (Python version).** A program can run a real web server. It listens on your own computer only (127.0.0.1) until you decide otherwise.

```
when someone visits the path home do
show a heading with the words Welcome end words
show a paragraph with the words Built in plain English. end words
reply with the page
end when
when someone visits the path hello do
reply with the words Hello end words followed by the visitor sent name
end when
start the server on port 8080
```

Run it with `python3 plainly.py run site.plain`, then open `http://127.0.0.1:8080`. Replies are plain text or a simple page, and page text is escaped so visitors cannot inject code.

**Frontend (browser version, `plainly-web.html`).** Programs can build live pages with `show a heading`, `show a paragraph called NAME`, `show a box called NAME`, `show a button called NAME`, and react with `when the button called NAME is clicked do ... end when`. See the Counter page and Greeter page examples.

**Connecting them (Python version).** A page the server sends can have boxes and buttons that ask the server for answers:

```
show a box called first
show a paragraph called answer with the words Type a number. end words
show a button with the words Add them end words that asks the path add and shows the reply in the paragraph called answer
```

When the button is pressed, whatever is typed in the boxes is sent to the path `add`, and the reply appears in the paragraph. The handler reads each box with `the visitor sent first`. See `examples/app.plain`.

The browser version (`plainly-web.html`) cannot run or call a server, because published pages are not allowed to reach other machines. Use the Python version for full apps.

Safety: the server only answers requests for its own address (this blocks sneaky sites), page text is escaped, and pages may only run the one built-in script that sends the button request.

## Remembering between visits (Python version)

A program can keep numbers, text, yes or no values, and lists of those, in a file that lasts after the program stops. Like every file, it must ask permission first.

```
allow remembering in the file memory.json
let visits be what I remember called visits as a number or else 0
let total be visits plus 1
remember total as visits
```

- `remember VALUE as NAME` saves a value under a one-word name.
- `what I remember called NAME as TYPE` gives back a `maybe`, because nothing may be saved yet. Use `or else` for a default, or `has a value as` to check.
- If a saved value has a different type than you ask for, you get nothing instead of a wrong value.
- The memory file is written safely, a damaged file stops the program instead of being overwritten, and a server handles one visit at a time so counts stay right.
- A program can use only one memory file, up to 1 MB.

See `examples/counter.plain` and `examples/notes.plain`, a notes app with a page, a button, a server, and a memory that lasts.

## A quick tour

Put each sentence on its own line. Close every block with `end` and the block name.

**Notes, saying, and values**

```
note this line is a comment
say the words Hello, world.
let age be 30
set age to age plus 1
add 5 to age
subtract 2 from age
```

Text is written as `the words ... end words`. If nothing follows on the line, `end words` can be left off.

**Maths and joining text**

`plus`, `minus`, `times`, `divided by`, `modulo`. Join text with `followed by` (adds a space) or `joined to` (no space).

```
say the words Age is end words followed by age
```

**Choices and loops**

```
if age is greater than 17 then
say the words adult end words
otherwise if age is at least 13 then
say the words teen end words
otherwise
say the words child end words
end if

while age is less than 40 do
add 1 to age
end while

repeat 3 times do
say the words hi end words
end repeat

for each score in scores do
say score
end for
```

Comparisons: `is`, `is not`, `is greater than`, `is less than`, `is at least`, `is at most`. Combine with `and`, `or`, `not`.

**Lists**

```
let scores be a list of 4 and 8 and 15
let more be an empty list of number
add 16 to scores
say entry 1 of scores
say length of scores
```

**Functions**

```
define area of width as number with height as number giving number
give back width times height
end define

say area of 3 with 4
```

**Records**

```
a record called item has name as text and price as number and quantity as number
let apple be a new item with name the words apple end words and price 3 and quantity 2
say price of apple
```

**Maybe values**

```
let found be parsed number of the words 42 end words
if found has a value as number then
say number plus 1
otherwise
say the words not a number end words
end if
let safe be found or else 0
```

Also: `no number` (nothing), `some 5` (a value inside a maybe).

**Files, with permission**

```
allow reading the file prices.txt
let prices be the numbers in the file prices.txt
say largest of prices
allow writing the file report.txt
write the words done end words to the file report.txt
```

Also: `the contents of the file NAME`, `the lines of the file NAME`. Files must be in the program's own folder.

**Input and built-ins**

`what the user types` reads a line of text. Built-in helpers: `length of`, `square root of`, `absolute value of`, `rounded of`, `largest of`, `smallest of`, `parsed number of`.

## How it keeps programs safe

- Types are checked before the program starts.
- There is no null and no way to reach into memory.
- Files cannot be touched without permission, checked both before and while running, and only files in the program's own folder can be used.
- Programs cannot reach the network, other programs, or the host system.
- Divide-by-zero, bad list positions and similar problems stop the program with a plain message.

This is a design goal and a prototype, not a security guarantee. Do not run untrusted code with it as your only protection.

## Limits

- `run` mode is Python underneath, so it is not fast. `native` is.
- `native` supports numbers, text, yes/no values, lists of numbers, functions, and all the control sentences. It does not yet support files, records, or maybe values, and says so if you use them.
- Native text uses memory that is never freed. Fine for normal programs, not for ones that run for days.
- Symbols such as colons, quotes and underscores are not allowed outside text. Inside `the words ... end words` you can use any symbols, except that the two words `end words` together always end the text.
- Text ends by itself before `followed by`, `joined to`, `that asks` and `and the words`. In other places, close it with `end words` when more of the sentence follows, for example `if said contains the words hello end words then`.
- A name can be up to 6 words and any words, but cannot start with a number or be `true` or `false`.
- Functions must be defined before they are used.

## Examples

See the `examples` folder: `hello`, `shop` (records, functions, loops), `files` (permissions), `speed` (a native benchmark), `maybe`, and `fizz`. Files starting with `bad` show errors on purpose.

## Contributing and license

Ideas and bug reports are welcome. Add a license of your choice before sharing widely; MIT is a common, simple option.
