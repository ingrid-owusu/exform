# exform cookbook

A gallery of copy-paste recipes. **Every command on this page is run in CI-style
verification before release** — the output shown is the real output.

New to exform? Read the [README](README.md) first. The one rule to remember:
**one example is often enough; two removes ambiguity.** If exform warns that it
had to hardcode part of your input, add a second example that varies that part.

Each recipe shows the program exform *inferred* (`--dry-run`) so you can see
there's no black box. Jump to a section:

- [Names & people](#names--people)
- [Numbers & IDs](#numbers--ids)
- [Text case & slugs](#text-case--slugs)
- [Web & files](#web--files)
- [CSV, columns & key/values](#csv-columns--keyvalues)
- [Dates](#dates)
- [Wrapping & templating](#wrapping--templating)

---

## Names & people

**"First Last" → "Last, Initial."**

```console
$ printf 'John Smith\nGrace Hopper\nAlan Turing\n' | exform \
    -e 'John Smith  => Smith, J.' -e 'Grace Hopper => Hopper, G.'
Smith, J.
Hopper, G.
Turing, A.
```

**"Last, First" → "First Last"** &nbsp;·&nbsp; `field(ws,1) + ' ' + field(,,0)`

```console
$ printf 'Smith, John\nDoe, Jane\n' | exform \
    -e 'Smith, John => John Smith' -e 'Doe, Jane => Jane Doe' -q
John Smith
Jane Doe
```

**Initials** &nbsp;·&nbsp; needs two examples so nothing is memorised

```console
$ printf 'Grace Hopper\nAlan Turing\n' | exform \
    -e 'Grace Hopper => G.H.' -e 'Alan Turing => A.T.' -q
G.H.
A.T.
```

**Acronym / initials that generalize to *any* number of words** &nbsp;·&nbsp; `line.acronym`

Give examples of different lengths and exform folds over every word instead of
memorising a fixed number of fields:

```console
$ printf 'Ada King Lovelace\nCher\nJohn Ronald Reuel Tolkien\n' | exform \
    -e 'John Ronald Tolkien => JRT' -e 'Alan Turing => AT' -q
AKL
C
JRRT
```

**Corporate username from a name** &nbsp;·&nbsp; `line.first_ + field(ws,1).lower`

```console
$ printf 'Grace Hopper\nAlan Turing\n' | exform \
    -e 'John Smith => jsmith' -e 'Ada Lovelace => alovelace' -q
ghopper
aturing
```

**Just the first name** &nbsp;·&nbsp; `field(ws,0)` &nbsp;·&nbsp; **just the last** &nbsp;·&nbsp; `field(ws,-1)`

```console
$ printf 'John Smith\nGrace Hopper\n' | exform -e 'John Smith => John'
John
Grace
```

## Numbers & IDs

**Extract the number from noisy text** &nbsp;·&nbsp; one example is enough

```console
$ printf 'Order #12345 shipped\nOrder #42 shipped\n' | exform -e 'Order #12345 shipped => 12345'
12345
42
```

**Add thousands separators** &nbsp;·&nbsp; `line.group,` &nbsp;·&nbsp; like a spreadsheet

```console
$ printf '1234567\n89012\n42\n' | exform -e '1234567 => 1,234,567'
1,234,567
89,012
42
```

**Money-style: prefix a `$` and group** &nbsp;·&nbsp; `'$' + line.group,`

```console
$ printf '1234567\n89012\n' | exform -e '1234567 => $1,234,567' -q
$1,234,567
$89,012
```

**Group a number buried in text**

```console
$ printf 'Total: 1234567 units\n' | exform -e 'Total: 1234567 units => 1,234,567'
1,234,567
```

**Zero-pad IDs to a fixed width** &nbsp;·&nbsp; `line.zpad3`

```console
$ printf '7\n42\n1000\n' | exform -e '7 => 007'
007
042
1000
```

## Text case & slugs

**Title-case a line** &nbsp;·&nbsp; `line.title` &nbsp;·&nbsp; **UPPERCASE** &nbsp;·&nbsp; `line.upper`

```console
$ printf 'hello world\nfoo bar baz\n' | exform -e 'hello world => Hello World'
Hello World
Foo Bar Baz
```

**Slugify for URLs/anchors** &nbsp;·&nbsp; `line.slug` &nbsp;·&nbsp; works for any number of words

```console
$ printf 'Hello World\nMy Post: Part 2\nQuick Brown Fox Jumps\n' | exform -e 'Hello World => hello-world'
hello-world
my-post-part-2
quick-brown-fox-jumps
```

**snake_case → kebab-case** &nbsp;·&nbsp; (also `line.snake` to go the other way)

```console
$ printf 'my_var_name\nfoo_bar\n' | exform -e 'my_var_name => my-var-name'
my-var-name
foo-bar
```

**snake_case → camelCase** &nbsp;·&nbsp; `line.camel` &nbsp;·&nbsp; folds over any number of words

Two examples of different word counts remove ambiguity; exform reshapes each
word rather than memorising a fixed number of fields (`line.pascal` gives
`MyVarName`). The word splitter accepts `snake_case`, `kebab-case`, spaced and
`camelCase` input alike.

```console
$ printf 'my_var_name\nhttp_request_id\nx\n' | exform \
    -e 'my_var_name => myVarName' -e 'foo_bar => fooBar' -q
myVarName
httpRequestId
x
```

**camelCase → snake_case** &nbsp;·&nbsp; `line.snakecase` &nbsp;·&nbsp; the reverse direction, splits on case boundaries

The same word splitter runs backwards: `camelCase` / `PascalCase` / `ACRONYM`
input folds to lower-cased `snake_case` (`line.snakecase`), `kebab-case`
(`line.kebabcase`), or spaced Title Case (`line.titlecase`).

```console
$ printf 'firstName\nuserId\ngetHTTPResponse\n' | exform \
    -e 'myVariableName => my_variable_name' -e 'firstName => first_name' -q
first_name
user_id
get_http_response
```

## Web & files

**Domain from a URL** &nbsp;·&nbsp; `field(/,2)`

```console
$ printf 'https://example.com/x\nhttp://foo.org/y\n' | exform \
    -e 'https://example.com/x => example.com' -e 'http://foo.org/y => foo.org'
example.com
foo.org
```

**Username from an email** &nbsp;·&nbsp; `field(@,0)`

```console
$ printf 'jane.doe@corp.com\nbob.lee@corp.com\n' | exform -e 'jane.doe@corp.com => jane.doe'
jane.doe
bob.lee
```

**Lowercase a whole email** &nbsp;·&nbsp; `line.lower`

```console
$ printf 'JANE@X.COM\nBob@Y.com\n' | exform -e 'JANE@X.COM => jane@x.com'
jane@x.com
bob@y.com
```

**Drop a file extension** &nbsp;·&nbsp; two examples pin the multi-dot case

```console
$ printf 'report.pdf\nphoto.jpeg\n' | exform \
    -e 'report.pdf => report' -e 'photo.jpeg => photo' -q
report
photo
```

**Strip a leading `@` from handles** &nbsp;·&nbsp; two examples so `_` is preserved

```console
$ printf '@alice\n@bob_dev\n' | exform -e '@alice => alice' -e '@bob_dev => bob_dev' -q
alice
bob_dev
```

## CSV, columns & key/values

**Reorder / relabel columns** &nbsp;·&nbsp; two examples pin down which fields move

```console
$ printf '2021,apple,5\n2022,pear,9\n' | exform \
    -e '2021,apple,5 => apple: 5' -e '2022,pear,9 => pear: 9'
apple: 5
pear: 9
```

**Swap two space-separated columns**

```console
$ printf 'a b\nc d\n' | exform -e 'a b => b a' -e 'c d => d c' -q
b a
d c
```

**Value from `key=value`** &nbsp;·&nbsp; `field(=,1)`

```console
$ printf 'name=jane\ncity=oslo\n' | exform -e 'name=jane => jane'
jane
oslo
```

## Dates

**ISO → US date, keep it simple**

```console
$ printf '2021-05-01\n2022-12-31\n' | exform \
    -e '2021-05-01 => 05/01/2021' -e '2022-12-31 => 12/31/2022' -q
05/01/2021
12/31/2022
```

**Reformat a date and drop a field from a log line**

```console
$ printf '2021-05-01 ERROR boom\n2022-12-31 WARN cold\n' | exform \
    -e '2021-05-01 ERROR boom => 01/05/2021 boom' \
    -e '2022-12-31 WARN cold => 31/12/2022 cold'
01/05/2021 boom
31/12/2022 cold
```

## Wrapping & templating

**Wrap each line in an HTML tag**

```console
$ printf 'hi\nyo\n' | exform -e 'hi => <li>hi</li>' -e 'yo => <li>yo</li>' -q
<li>hi</li>
<li>yo</li>
```

**Turn URLs into Markdown links**

```console
$ printf 'https://a.com\nhttps://b.org\n' | exform \
    -e 'https://a.com => [a.com](https://a.com)' \
    -e 'https://b.org => [b.org](https://b.org)' -q
[a.com](https://a.com)
[b.org](https://b.org)
```

**Quote a CSV field**

```console
$ printf 'a,1\nb,2\n' | exform -e 'a,1 => "a"' -e 'b,2 => "b"' -q
"a"
"b"
```

## In-line edits (`--in-line`) — change only what differs

These leave the rest of each line untouched, like `sed` but by example.

**Reformat a date inside a line**

```console
$ printf 'commit 2021-03-05 ok\npush 1999-12-31 x\n' \
    | exform --in-line -e 'commit 2021-03-05 ok => commit 2021/03/05 ok'
commit 2021/03/05 ok
push 1999/12/31 x
```

**Uppercase a keyed value, nothing else**

```console
$ printf 'level=info a\nlevel=warn b\n' \
    | exform --in-line -e 'level=info a => level=INFO a' -e 'level=warn b => level=WARN b'
level=INFO a
level=WARN b
```

**Wrap a word in brackets**

```console
$ printf 'see foo here\nsee bar there\n' \
    | exform --in-line -e 'see foo here => see <foo> here' -e 'see bar there => see <bar> there'
see <foo> here
see <bar> there
```

**Rewrite every match on a line (`--all`)**

```console
$ printf 'a 1 2 3 b\n' | exform --in-line --all -e 'a 1 b => a [1] b'
a [1] [2] [3] b
```

**Reshape one column of a CSV/TSV (`--field`)**

```console
$ printf 'id,date,amt\n1,2021-05-01,100\n2,2022-12-31,250\n' \
    | exform --field 2 -e '2021-05-01 => 05/01/2021' -e '2022-12-31 => 12/31/2022'
id,date,amt
1,05/01/2021,100
2,12/31/2022,250
```

Only column 2 changes; the other columns (and the header) are left exactly as
they were. Use `--field-sep $'\t'` for TSV, and `--field 2,4` to reshape several
columns at once.

```console
$ printf 'name\tcity\nJOHN\tnyc\nJANE\tla\n' \
    | exform --field 1 --field-sep $'\t' -e 'JOHN => John' -e 'JANE => Jane'
name	city
John	nyc
Jane	la
```

**Emit a standalone, dependency-free script (`--emit python`)**

```console
$ exform -e 'my_var_name => myVarName' -e 'home_address => homeAddress' --emit python > camelize.py
$ printf 'deep_nested_key\n' | python3 camelize.py
deepNestedKey
```

The generated `camelize.py` has no dependency on exform — commit it and run it
anywhere Python is available. exform verifies the script reproduces your
examples before printing it.

---

Got a recipe exform can't learn, or one worth adding? Open an issue — the
maintainer (an AI agent) reads them. If a mapping is genuinely ambiguous from
your examples, exform will tell you what it had to assume; add one more varied
example and it usually locks on.
