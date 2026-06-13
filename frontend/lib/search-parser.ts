export type TokenType = 'AND' | 'OR' | 'NOT' | 'LPAREN' | 'RPAREN' | 'TERM' | 'WS';

export interface Token {
  type: TokenType;
  value: string;
  field?: string;
  exact?: boolean;
  isRegex?: boolean;
  start: number;
  end: number;
}

export interface ParseError {
  message: string;
  position: number;
}

const TOKEN_REGEX_STR = [
  "(?<LPAREN>\\()",
  "(?<RPAREN>\\))",
  "(?<AND>\\bAND\\b)",
  "(?<OR>\\bOR\\b)",
  "(?<NOT>\\bNOT\\b|-)",
  "(?<TERM_EXPR>(?<key>[a-zA-Z0-9_]+:)?(?:/(?<regex>(?:\\\\/|[^/])+)/|\"(?<dquote>(?:\\\\\"|[^\"])+)\"|'(?<squote>(?:\\\\'|[^'])+)'|(?<unquoted>(?!(?:title|message|sender|severity|tag|after|before):)[^\\s()\\/\"'][^\\s()]*)))",
  "(?<WS>\\s+)"
].join("|");

const TOKEN_REGEX = new RegExp(TOKEN_REGEX_STR, "gi");

export function tokenize(query: string): Token[] {
  const tokens: Token[] = [];
  let match;
  let expectedIndex = 0;
  
  // reset regex state
  TOKEN_REGEX.lastIndex = 0;

  while ((match = TOKEN_REGEX.exec(query)) !== null) {
    if (match.index > expectedIndex) {
      throw { message: `Unexpected character '${query.slice(expectedIndex, match.index)}'`, position: expectedIndex };
    }
    expectedIndex = TOKEN_REGEX.lastIndex;

    if (!match.groups) continue;
    
    const start = match.index;
    const end = TOKEN_REGEX.lastIndex;
    const value = match[0];
    const g = match.groups;

    if (g.WS) {
      // skip whitespace
      continue;
    } else if (g.LPAREN) {
      tokens.push({ type: 'LPAREN', value, start, end });
    } else if (g.RPAREN) {
      tokens.push({ type: 'RPAREN', value, start, end });
    } else if (g.AND) {
      tokens.push({ type: 'AND', value: 'AND', start, end });
    } else if (g.OR) {
      tokens.push({ type: 'OR', value: 'OR', start, end });
    } else if (g.NOT) {
      tokens.push({ type: 'NOT', value: 'NOT', start, end });
    } else if (g.TERM_EXPR) {
      const key = g.key;
      const field = key ? key.slice(0, -1).toLowerCase() : undefined;
      
      let termVal = "";
      let exact = false;
      let isRegex = false;

      if (g.regex !== undefined) {
        termVal = g.regex.replace(/\\\//g, '/');
        isRegex = true;
      } else if (g.dquote !== undefined) {
        termVal = g.dquote.replace(/\\"/g, '"');
        exact = true;
      } else if (g.squote !== undefined) {
        termVal = g.squote.replace(/\\'/g, "'");
        exact = true;
      } else if (g.unquoted !== undefined) {
        termVal = g.unquoted;
      }

      tokens.push({ type: 'TERM', value: termVal, field, exact, isRegex, start, end });
    }
  }

  if (expectedIndex < query.length) {
    throw { message: `Unexpected character '${query.slice(expectedIndex)}'`, position: expectedIndex };
  }

  return tokens;
}

export function validateQuery(query: string): ParseError | null {
  if (!query || !query.trim()) return null;

  let tokens: Token[] = [];
  try {
    tokens = tokenize(query);
  } catch (err: any) {
    return { message: "Invalid syntax", position: 0 };
  }

  let pos = 0;

  function peek(): Token | null {
    return pos < tokens.length ? tokens[pos] : null;
  }

  function consume(): Token {
    return tokens[pos++];
  }

  function parseOr() {
    parseAnd();
    while (peek()?.type === 'OR') {
      consume();
      parseAnd();
    }
  }

  function parseAnd() {
    parseNot();
    while (peek()) {
      const t = peek()!;
      if (t.type === 'AND') {
        consume();
        parseNot();
      } else if (t.type === 'TERM' || t.type === 'LPAREN' || t.type === 'NOT') {
        parseNot();
      } else {
        break;
      }
    }
  }

  function parseNot() {
    const t = peek();
    if (t?.type === 'NOT') {
      consume();
      parsePrimary();
    } else {
      parsePrimary();
    }
  }

  function parsePrimary() {
    const t = peek();
    if (!t) {
      throw { message: "Unexpected end of query", position: query.length };
    }
    
    if (t.type === 'LPAREN') {
      consume();
      parseOr();
      const next = peek();
      if (!next || next.type !== 'RPAREN') {
        throw { message: "Missing closing parenthesis ')'", position: next ? next.start : query.length };
      }
      consume();
      return;
    }
    
    if (t.type === 'TERM') {
      if (t.isRegex) {
        try {
          new RegExp(t.value);
        } catch (e: any) {
          throw { message: `Invalid regex: ${e.message}`, position: t.start };
        }
      }
      consume();
      return;
    }
    
    throw { message: `Unexpected token '${t.value}'`, position: t.start };
  }

  try {
    parseOr();
    if (pos < tokens.length) {
      throw { message: `Unexpected token '${tokens[pos].value}'`, position: tokens[pos].start };
    }
    return null;
  } catch (err: any) {
    if (err.message && err.position !== undefined) {
      return err as ParseError;
    }
    return { message: "Syntax error", position: query.length };
  }
}

export function highlightQueryHtml(query: string): string {
  // We can rebuild the query with highlighted tokens
  // but to preserve exact spacing, we just wrap tokens based on their start/end
  if (!query) return "";
  
  const tokens = tokenize(query);
  let html = "";
  let lastIndex = 0;

  for (const t of tokens) {
    // Add whitespace
    if (t.start > lastIndex) {
      html += escapeHtml(query.slice(lastIndex, t.start));
    }
    
    const tokenStr = escapeHtml(query.slice(t.start, t.end));
    
    if (t.type === 'AND' || t.type === 'OR' || t.type === 'NOT') {
      html += `<span class="text-primary font-bold">${tokenStr}</span>`;
    } else if (t.type === 'LPAREN' || t.type === 'RPAREN') {
      html += `<span class="text-muted-foreground">${tokenStr}</span>`;
    } else if (t.type === 'TERM') {
      if (t.field) {
        const colonIdx = tokenStr.indexOf(':');
        const fieldPart = tokenStr.slice(0, colonIdx + 1);
        const valPart = tokenStr.slice(colonIdx + 1);
        
        let valClass = "text-foreground";
        if (t.isRegex) valClass = "text-amber-500";
        else if (t.exact) valClass = "text-emerald-500";
        
        html += `<span class="text-blue-500">${fieldPart}</span><span class="${valClass}">${valPart}</span>`;
      } else {
        let valClass = "text-foreground";
        if (t.isRegex) valClass = "text-amber-500";
        else if (t.exact) valClass = "text-emerald-500";
        
        html += `<span class="${valClass}">${tokenStr}</span>`;
      }
    }
    
    lastIndex = t.end;
  }
  
  if (lastIndex < query.length) {
    html += escapeHtml(query.slice(lastIndex));
  }
  
  return html;
}

function escapeHtml(str: string): string {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
