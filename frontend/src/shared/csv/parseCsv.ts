export type CsvRow = { line: number; cells: string[] };
export type CsvParseError = { line: number; column: number; reason: string };
export type CsvParseResult = { rows: CsvRow[]; errors: CsvParseError[] };

// A strict RFC 4180-style parser. It preserves blank rows and reports malformed
// quoting instead of silently dropping or shifting columns.
export function parseCsv(input: string): CsvParseResult {
  const text = input.replace(/^\uFEFF/, "");
  const rows: CsvRow[] = [];
  const errors: CsvParseError[] = [];
  let cells: string[] = [];
  let field = "";
  let quoted = false;
  let afterQuote = false;
  let line = 1;
  let rowLine = 1;
  let column = 1;
  let rowStarted = false;

  const addField = () => {
    cells.push(field);
    field = "";
    afterQuote = false;
  };
  const addRow = () => {
    addField();
    rows.push({ line: rowLine, cells });
    cells = [];
    rowStarted = false;
  };

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    const newline = char === "\n" || char === "\r";
    const pair = char === "\r" && next === "\n";
    if (quoted) {
      if (char === '"') {
        if (next === '"') {
          field += '"';
          index += 1;
          column += 2;
        } else {
          quoted = false;
          afterQuote = true;
          column += 1;
        }
      } else if (newline) {
        field += "\n";
        if (pair) index += 1;
        line += 1;
        column = 1;
      } else {
        field += char;
        column += 1;
      }
      continue;
    }

    if (char === ",") {
      addField();
      rowStarted = true;
      column += 1;
      continue;
    }
    if (newline) {
      addRow();
      if (pair) index += 1;
      line += 1;
      rowLine = line;
      column = 1;
      continue;
    }
    if (afterQuote) {
      errors.push({
        line,
        column,
        reason: "Unexpected character after closing quote",
      });
      afterQuote = false;
    }
    if (char === '"') {
      if (field.length === 0) quoted = true;
      else errors.push({ line, column, reason: "Quote inside unquoted field" });
    } else {
      field += char;
    }
    rowStarted = true;
    column += 1;
  }
  if (quoted)
    errors.push({ line, column, reason: "Unterminated quoted field" });
  if (rowStarted || cells.length > 0 || field.length > 0 || afterQuote)
    addRow();
  return { rows, errors };
}
