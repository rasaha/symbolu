# Final BASE-MD Markdown Grammar (BASE-MD/1.0)

- **grammar file:** `grammar/base-markdown.ebnf` = `sha-256:033317aff402f86b7073e75e821aec8954c49e31ffae735776a5b6e6d9273b49`
- **semantics file:** `grammar/base-markdown-semantics.json` = `sha-256:06399e60c4b855cf763f07de0d66022947ba2958b2567fe639fae3784e1e658f`
- **nonterminals defined:** 40
- **self-containment:** every nonterminal referenced on a right-hand side is defined in the
  same file (validator §9 reported zero undefined references).

The grammar is a complete self-contained PEG. It defines the accepted Markdown surface
(documents, ATX headings, blockquotes, ordered/unordered lists, tables, fenced code, link
and footnote definitions, paragraphs, and the inline layer: strong/emphasis/reference &
inline links/footnote refs/escapes/text) down to terminal character classes (`Char`, `WS`,
`LineEnd`, `EOF`, `URL`, `Id`, `Number`, `Indent`). Nonterminals:

```
ATXHeading, Alnum, AnyLine, BlankLine, Block, Blockquote, CellText, Char, DataRow, DelimiterRow, Digit, Document, EOF, Emphasis, Escape, Fence, FencedCode, FootnoteDef, FootnoteRef, Hash, HeaderRow, Id, Indent, Inline, InlineLink, Lang, LineEnd, LinkDef, Number, OList, Paragraph, Punct, RefLink, SpecialStart, Strong, Table, Text, UList, URL, WS
```

Companion semantics (`base-markdown-semantics.json`) fixes how parsed blocks map to
assertion-bearing vs non-assertive units (headings-as-clauses, list fragments, table rows,
code blocks, quotations) consistently with the B/Z corpus groups.

Full grammar source:

```peg
(* BASE-MD/1.0 - complete self-contained PEG grammar. Every nonterminal defined. *)
Document    <- Block* EOF
Block       <- FencedCode / ATXHeading / Blockquote / Table / OList / UList / LinkDef / FootnoteDef / Paragraph / BlankLine
BlankLine   <- WS* LineEnd
ATXHeading  <- Hash ' ' Inline+ LineEnd
Hash        <- '#' '#'? '#'? '#'? '#'? '#'?
Blockquote  <- ('>' ' '? Inline* LineEnd)+
OList       <- (Indent? Number ('.' / ')') ' ' Inline+ LineEnd)+
UList       <- (Indent? ('-' / '*' / '+') ' ' Inline+ LineEnd)+
Table       <- HeaderRow DelimiterRow DataRow+
HeaderRow   <- '|' (CellText '|')+ LineEnd
DelimiterRow<- '|' (WS* '-'+ WS* '|')+ LineEnd
DataRow     <- '|' (CellText '|')+ LineEnd
CellText    <- (!'|' !LineEnd Char)*
FencedCode  <- Fence Lang? LineEnd (!Fence AnyLine)* Fence LineEnd
Fence       <- '```'
Lang        <- (!LineEnd Char)+
LinkDef     <- '[' Id ']' ':' ' ' URL LineEnd
FootnoteDef <- '[^' Id ']' ':' ' ' Inline+ LineEnd
Paragraph   <- (Inline+ LineEnd)+ (BlankLine / EOF)
Inline      <- Strong / Emphasis / RefLink / InlineLink / FootnoteRef / Escape / Text
Strong      <- ('**' (!'**' Inline)+ '**') / ('__' (!'__' Inline)+ '__')
Emphasis    <- ('*' (!'*' Inline)+ '*') / ('_' (!'_' Inline)+ '_')
InlineLink  <- '[' Text ']' '(' URL ')'
RefLink     <- '[' Text ']' '[' Id ']'
FootnoteRef <- '[^' Id ']'
Escape      <- '\\' Punct
Text        <- (!SpecialStart Char)+
SpecialStart<- '**' / '__' / '*' / '_' / '[' / '`' / '\\' / LineEnd
Id          <- (Alnum / '-' / '_')+
URL         <- (!')' !WS !LineEnd Char)+
Number      <- Digit+
Digit       <- '0'..'9'
Alnum       <- 'a'..'z' / 'A'..'Z' / Digit
Indent      <- (' ' ' ' / '\t')
Punct       <- '!'..'/' / ':'..'@' / '['..'`' / '{'..'~'
WS          <- ' ' / '\t'
Char        <- !LineEnd .
AnyLine     <- (!LineEnd .)* LineEnd
LineEnd     <- '\n' / '\r\n'
EOF         <- !.
```
