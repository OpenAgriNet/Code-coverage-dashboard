// A small .xlsx writer, so the page loads no third-party code: sheets of rows in, an Excel workbook out. Each sheet gets a bold,
// frozen header row with filter buttons and column widths fitted to the text. Numbers stay numbers; everything else is text.
// The zip is stored, not compressed: the workbooks are small and Excel reads stored entries.
(function (root) {
  const enc = new TextEncoder();
  const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc32 = b => { let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };

  function zip(files) {   // [[path, Uint8Array]] -> Uint8Array
    const parts = [], dir = []; let off = 0;
    for (const [name, data] of files) {
      const n = enc.encode(name), crc = crc32(data);
      const h = new DataView(new ArrayBuffer(30));
      h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0x0800, true);   // UTF-8 names
      h.setUint16(10, 0, true); h.setUint16(12, 0x21, true);   // 1980-01-01 00:00
      h.setUint32(14, crc, true); h.setUint32(18, data.length, true); h.setUint32(22, data.length, true); h.setUint16(26, n.length, true);
      const c = new DataView(new ArrayBuffer(46));
      c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint16(8, 0x0800, true);
      c.setUint16(14, 0x21, true); c.setUint32(16, crc, true); c.setUint32(20, data.length, true); c.setUint32(24, data.length, true);
      c.setUint16(28, n.length, true); c.setUint32(42, off, true);
      parts.push(new Uint8Array(h.buffer), n, data); dir.push(new Uint8Array(c.buffer), n);
      off += 30 + n.length + data.length;
    }
    const size = dir.reduce((s, b) => s + b.length, 0), e = new DataView(new ArrayBuffer(22));
    e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true); e.setUint16(10, files.length, true);
    e.setUint32(12, size, true); e.setUint32(16, off, true);
    const all = [...parts, ...dir, new Uint8Array(e.buffer)], out = new Uint8Array(all.reduce((s, b) => s + b.length, 0));
    let p = 0; for (const b of all) { out.set(b, p); p += b.length; }
    return out;
  }

  // XML 1.0 has no place for most control characters; Excel caps a cell at 32,767 characters
  const xml = s => String(s).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F￾￿]/g, '').slice(0, 32767)
    .replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const col = i => { let s = ''; for (i++; i; i = Math.floor((i - 1) / 26)) s = String.fromCharCode(65 + (i - 1) % 26) + s; return s; };
  // sheet names: 31 characters, none of []:*?/\ , unique
  function names(sheets) {
    const seen = new Set();
    return sheets.map((s, i) => {
      const base = String(s.name || `Sheet${i + 1}`).replace(/[[\]:*?/\\]/g, ' ').trim().slice(0, 31) || `Sheet${i + 1}`;
      let n = base; for (let k = 2; seen.has(n.toLowerCase()); k++) n = base.slice(0, 31 - String(k).length - 1) + '~' + k;
      seen.add(n.toLowerCase()); return n;
    });
  }
  function cell(v, r, c, header) {
    const ref = col(c) + (r + 1);
    if (v == null || v === '') return '';
    if (typeof v === 'number' && Number.isFinite(v) && !header) return `<c r="${ref}"><v>${v}</v></c>`;
    if (typeof v === 'boolean') v = v ? 'Yes' : 'No';
    return `<c r="${ref}" t="inlineStr"${header ? ' s="1"' : ''}><is><t xml:space="preserve">${xml(v)}</t></is></c>`;
  }
  function sheet(rows) {
    const width = Math.max(1, ...rows.map(r => r.length));
    const w = Array.from({ length: width }, (_, c) => Math.min(60, Math.max(8, ...rows.slice(0, 500).map(r => String(r[c] ?? '').length + 2))));
    const last = col(width - 1) + Math.max(1, rows.length);
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
      + (rows.length > 1 ? '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>' : '')
      + `<cols>${w.map((x, i) => `<col min="${i + 1}" max="${i + 1}" width="${x}" customWidth="1"/>`).join('')}</cols>`
      + `<sheetData>${rows.map((r, i) => `<row r="${i + 1}">${r.map((v, c) => cell(v, i, c, i === 0)).join('')}</row>`).join('')}</sheetData>`
      + (rows.length > 1 ? `<autoFilter ref="A1:${last}"/>` : '')
      + '</worksheet>';
  }

  // sheets: [{name, rows: [[header...], [value...], ...]}] -> the .xlsx file's bytes
  function build(sheets) {
    const n = names(sheets), u = s => enc.encode(s);
    const files = [
      ['[Content_Types].xml', u('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        + '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
        + '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + n.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')
        + '</Types>')],
      ['_rels/.rels', u('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')],
      ['xl/workbook.xml', u('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        + n.map((x, i) => `<sheet name="${xml(x)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join('') + '</sheets>'
        + `<definedNames>${n.map((x, i) => sheets[i].rows.length > 1 ? `<definedName name="_xlnm._FilterDatabase" localSheetId="${i}" hidden="1">'${xml(x.replace(/'/g, "''"))}'!$A$1:$${col(Math.max(1, ...sheets[i].rows.map(r => r.length)) - 1)}$${sheets[i].rows.length}</definedName>` : '').join('')}</definedNames>`
        + '</workbook>')],
      ['xl/_rels/workbook.xml.rels', u('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + n.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join('')
        + `<Relationship Id="rId${n.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`)],
      ['xl/styles.xml', u('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        + '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        + '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
        + '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        + '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        + '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
        + '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        + '</styleSheet>')],
      ...sheets.map((s, i) => [`xl/worksheets/sheet${i + 1}.xml`, u(sheet(s.rows))]),
    ];
    return zip(files);
  }
  function download(filename, sheets) {
    const url = URL.createObjectURL(new Blob([build(sheets)], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }));
    const a = document.createElement('a'); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const lib = { build, download, names };
  if (typeof module !== 'undefined' && module.exports) module.exports = lib; else root.Xlsx = lib;
})(typeof window !== 'undefined' ? window : globalThis);
