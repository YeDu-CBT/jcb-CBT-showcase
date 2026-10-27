const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  BorderStyle, ShadingType, ExternalHyperlink, Header, Footer, PageNumber,
  LevelFormat, convertInchesToTwip,
  Table, TableRow, TableCell, WidthType, TableLayoutType, LineRuleType, ImageRun,
} = require("docx");

const RAW_DIR = path.join(__dirname, "raw");   // __dirname = 이 스크립트가 있는 폴더(jcb_restored)
const OUT_PATH = path.join(__dirname, "정보처리기사_실기_복원문제_2020-2026.docx");

const files = fs.readdirSync(RAW_DIR)
  .filter(f => f.endsWith(".json"))
  .sort((a, b) => {
    const [ya, ra] = a.replace(".json", "").split("_").map(Number);
    const [yb, rb] = b.replace(".json", "").split("_").map(Number);
    return ya - yb || ra - rb;
  });

const rounds = files.map(f => JSON.parse(fs.readFileSync(path.join(RAW_DIR, f), "utf-8")));

// 지시문/본문/보기 분리 결과 (python3 format_prompts.py --dump formatted_prompts.json 으로 생성)
const FORMATTED = JSON.parse(fs.readFileSync(path.join(__dirname, "formatted_prompts.json"), "utf-8"));
// 해설 줄 나누기 결과 (python3 format_prompts.py --dump formatted_prompts.json --dump-expl formatted_explanations.json)
const EXPL = JSON.parse(fs.readFileSync(path.join(__dirname, "formatted_explanations.json"), "utf-8"));
// code 칸에 들어 있는 파이프 표 (python3 format_prompts.py ... --dump-ctable formatted_code_tables.json)
const CTABLES = JSON.parse(fs.readFileSync(path.join(__dirname, "formatted_code_tables.json"), "utf-8"));
const TEXT_W = 11906 - 1134 * 2;   // A4 폭 - 좌우 여백 = 본문 폭(DXA)

const totalQ = rounds.reduce((s, r) => s + r.questions.length, 0);
const totalImg = rounds.reduce((s, r) => s + (r.image_only_questions || []).length, 0);

const FONT = "맑은 고딕";
const CODE_FONT = "Consolas";

function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.after ?? 120 },
    children: [new TextRun({ text, font: FONT, size: opts.size ?? 21, bold: !!opts.bold, color: opts.color })],
    ...opts.paraProps,
  });
}

function labelLine(label, text) {
  return new Paragraph({
    spacing: { after: 80 },
    children: [
      new TextRun({ text: label + " ", bold: true, font: FONT, size: 21 }),
      new TextRun({ text: text, font: FONT, size: 21 }),
    ],
  });
}

// 표(파이프 표기를 복원한 것): rows[0] 이 머리글. 열 너비는 글자 수에 비례(좁은 열은 그대로, 넓은 열이 남는 폭을 나눠 가짐).
function dispUnits(t) {           // 한글 등 전각은 2, 나머지는 1로 센 표시 폭
  let u = 0;
  for (const ch of t) u += /[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af\u3000-\u303f\uff00-\uffef\u2460-\u24ff]/.test(ch) ? 2 : 1;
  return u;
}
function colWidths(rows) {
  const ncol = rows[0].length;
  const UNIT = 130, PAD = 380;                    // 반각 한 칸 ≈ 130 DXA(폰트 대체·굵은 머리글까지 감안해 넉넉히), 좌우 여백 합 380
  const nat = [];
  for (let c = 0; c < ncol; c++) nat.push(Math.max(...rows.map(r => dispUnits(r[c]))) * UNIT + PAD);
  const sum = nat.reduce((a, b) => a + b, 0);
  if (sum <= TEXT_W) return nat;                   // 다 들어가면 자연 폭 그대로(표가 쪽 폭을 억지로 채우지 않음)
  // 넘치면: 좁은 열부터 자연 폭을 보장하고, 남은 폭을 나머지(넓은) 열이 자연 폭 비율로 나눠 가진다
  const idx = nat.map((w, i) => i).sort((a, b) => nat[a] - nat[b]);
  const res = new Array(ncol).fill(0);
  let remain = TEXT_W, left = idx.slice();
  while (left.length) {
    const share = remain / left.length;
    const c = left[0];
    if (nat[c] <= share) { res[c] = nat[c]; remain -= nat[c]; left.shift(); }
    else {
      const tot = left.reduce((a, i) => a + nat[i], 0);
      left.forEach(i => { res[i] = Math.floor(remain * nat[i] / tot); });
      break;
    }
  }
  return res;
}
function tableBlock(rows, caption, header = true) {
  const out = [];
  if (caption) {
    out.push(new Paragraph({
      spacing: { after: 60 }, keepNext: true,
      children: [new TextRun({ text: caption, font: FONT, size: 21 })],
    }));
  }
  const widths = colWidths(rows);
  const total = widths.reduce((a, b) => a + b, 0);
  const edge = { style: BorderStyle.SINGLE, size: 4, color: "666666" };
  const keepAll = rows.length <= 12;              // 작은 표는 쪽을 가로지르지 않게 행끼리 붙여 둔다
  const trs = rows.map((r, ri) => new TableRow({
    tableHeader: header && ri === 0,
    cantSplit: true,
    children: r.map((t, ci) => new TableCell({
      width: { size: widths[ci], type: WidthType.DXA },
      borders: { top: edge, bottom: edge, left: edge, right: edge },
      margins: { top: 60, bottom: 60, left: 110, right: 110 },
      shading: header && ri === 0 ? { type: ShadingType.CLEAR, fill: "EDEFF2", color: "auto" } : undefined,
      children: [new Paragraph({
        spacing: { after: 0 },
        keepNext: keepAll && ri < rows.length - 1,
        children: [new TextRun({ text: t, font: FONT, size: 21, bold: header && ri === 0 })],
      })],
    })),
  }));
  out.push(new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    layout: TableLayoutType.FIXED,
    rows: trs,
  }));
  out.push(new Paragraph({ spacing: { before: 0, after: 0, line: 120, lineRule: LineRuleType.EXACT }, children: [] }));
  return out;
}

// 문제 지문: 블록(지시문/본문/보기) 사이는 간격, 블록 안의 줄은 각각 별도 문단.
// box=true 인 연속 블록(지시문의 '다음/아래'가 가리키는 본문)은 직사각형 테두리 상자(1칸짜리 표) 안에 넣는다.
function promptBlocks(blocks, tailNext = false) {
  const out = [];
  const edge = { style: BorderStyle.SINGLE, size: 6, color: "444444" };
  let i = 0;
  while (i < blocks.length) {
    const b = blocks[i];
    if (b.kind === "table") {
      out.push(...tableBlock(b.rows, b.caption, b.header !== false));
      i++;
      continue;
    }
    if (b.box) {
      const grp = [];
      while (i < blocks.length && blocks[i].box && blocks[i].kind !== "table") { grp.push(blocks[i]); i++; }
      const cellParas = [];
      grp.forEach((g, gi) => {
        const lastBlock = gi === grp.length - 1;
        if (g.kind === "image") {                // 다시 그린 그림: 박스 안 가운데 정렬 + 작은 회색 캡션
          const sc = Math.min(0.5, 560 / g.w, 400 / g.h);          // 원본 PNG는 2배 해상도로 그려 둠 → 폭 최대 560px·높이 최대 400px
          cellParas.push(new Paragraph({
            alignment: AlignmentType.CENTER,
            keepNext: true,
            spacing: { before: 40, after: 40 },
            children: [new ImageRun({
              type: "png",
              data: fs.readFileSync(path.join(__dirname, g.file)),
              transformation: { width: Math.round(g.w * sc), height: Math.round(g.h * sc) },
              altText: { title: g.alt, description: g.alt, name: path.basename(g.file) },
            })],
          }));
          cellParas.push(new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { after: lastBlock ? 0 : 100 },
            children: [new TextRun({ text: g.caption || "", font: FONT, size: 16, color: "777777" })],
          }));
          return;
        }
        g.lines.forEach((t, li) => {
          const lastLine = li === g.lines.length - 1;
          cellParas.push(new Paragraph({
            spacing: { after: lastLine ? (lastBlock ? 0 : 100) : 20 },
            children: [new TextRun({ text: t, font: FONT, size: 21 })],
          }));
        });
      });
      out.push(new Table({
        width: { size: TEXT_W, type: WidthType.DXA },
        columnWidths: [TEXT_W],
        layout: TableLayoutType.FIXED,
        rows: [new TableRow({
          cantSplit: true,                       // 박스가 쪽 경계에서 갈라지지 않게(통째로 다음 쪽으로)
          children: [new TableCell({
            width: { size: TEXT_W, type: WidthType.DXA },
            borders: { top: edge, bottom: edge, left: edge, right: edge },
            margins: { top: 100, bottom: 100, left: 160, right: 160 },
            children: cellParas,
          })],
        })],
      }));
      // 표 바로 뒤의 얇은 간격(6pt 고정 높이)
      out.push(new Paragraph({ spacing: { before: 0, after: 0, line: 120, lineRule: LineRuleType.EXACT }, children: [] }));
      continue;
    }
    const nextIsBox = i + 1 < blocks.length ? (blocks[i + 1].box || blocks[i + 1].kind === "table") : tailNext;
    b.lines.forEach((t, li) => {
      const last = li === b.lines.length - 1;
      out.push(new Paragraph({
        spacing: { after: last ? 100 : 20 },
        keepNext: (last && i === blocks.length - 1) ? tailNext : true,   // 지시문·도입 문장이 쪽 맨 아래에 홀로 남지 않게(뒤의 박스/표와 같은 쪽에 붙임)
        indent: b.kind === "opt" ? { left: convertInchesToTwip(0.25) } : undefined,
        children: [new TextRun({ text: t, font: FONT, size: 21 })],
      }));
    });
    i++;
  }
  return out;
}

function codeBlock(code) {
  const lines = code.split("\n");
  return lines.map((line, i) => new Paragraph({
    spacing: { after: i === lines.length - 1 ? 120 : 0 },
    shading: { type: ShadingType.CLEAR, fill: "F2F2F2" },
    indent: { left: convertInchesToTwip(0.25) },
    children: [new TextRun({ text: line.length ? line : " ", font: CODE_FONT, size: 19 })],
  }));
}

const children = [];

// ---- 표지/개요 ----
children.push(new Paragraph({
  heading: HeadingLevel.TITLE,
  spacing: { after: 240 },
  children: [new TextRun({ text: "정보처리기사 실기 복원문제 모음", font: FONT, bold: true })],
}));
children.push(new Paragraph({
  spacing: { after: 360 },
  children: [new TextRun({ text: "2020년 1회 ~ 2026년 2회", font: FONT, size: 28, color: "555555" })],
}));

children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { after: 160 }, children: [new TextRun({ text: "출처 및 라이선스", font: FONT, bold: true })] }));
children.push(labelLine("원저작자:", "Life-Journey (블로그: chobopark.tistory.com)"));
children.push(labelLine("라이선스:", "CC BY (저작자표시) — 2020년 1회 글과 2026년 2회 글에서 직접 확인했으며, 같은 블로그의 나머지 글도 동일한 설정일 것으로 추정(개별 재확인은 하지 않음)"));
children.push(labelLine("수집 방법:", "각 회차 블로그 글을 AI 웹 열람 도구로 읽어 받아쓰기(transcribe)함. 원문 HTML을 직접 대조한 완전 검증은 아니며, 일부 코드 문제는 사용자가 보유한 별도의 독립적 자료(다른 저자의 기출풀이집)와 대조해 일치를 확인함."));
children.push(labelLine("보완 이력:", "2026-10-08 원문 페이지와 2차 대조하여 165문항을 보완함 — 표·그림이 빠져 있던 57문항(A), 보기·본문이 빠져 있던 79문항(B), 이미지 전용이라 제외했던 13문항을 새로 추가(C), 원문과 표기가 달랐던 16문항(D, 표기 차이는 원문대로 반영. 다만 문제 풀이를 틀어지게 하는 코드 오타는 고침: 2020-1 문제 6·2022-3 문제 12의 'SELECT DERP'는 'SELECT DEPT'로 수정). 표는 진짜 표로 옮겼고, 그림은 원문을 보고 다시 그려 '▲ 원문 그림을 보고 다시 그린 도식'이라고 표시함(원문 그림과 세부 모양·배치가 다를 수 있으니 원문 링크로 확인). 원문 페이지 자체에 보기가 실려 있지 않은 문항은 '(실제 기출문제에서는 보기가 주어집니다)' 같은 원문 안내만 남아 있음."));
children.push(labelLine("수집 범위:", `총 ${rounds.length}개 회차, ${totalQ}문제 수집` + (totalImg ? ` / ${totalImg}문제는 원문이 이미지(표·다이어그램)로만 되어 있어 제외` : " (원문이 표·그림으로만 되어 있던 문제도 표는 표로, 그림은 다시 그려 포함)")));
children.push(new Paragraph({
  spacing: { after: 360 },
  children: [new TextRun({ text: "주의: 이 문서는 학습 참고용으로 정리한 것이며, 정답의 정확성을 100% 보장하지 않습니다. 실제 복원문제 특성상(응시자의 기억에 의존) 원 시험과 세부 표현이 다를 수 있습니다.", italics: true, color: "B00000", font: FONT, size: 20 })],
}));

// ---- 목차 ----
children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { after: 160 }, children: [new TextRun({ text: "목차", font: FONT, bold: true })] }));
for (const r of rounds) {
  const nImg = (r.image_only_questions || []).length;
  const label = `${r.year}년 ${r.round}회 — ${r.questions.length}문제${nImg ? `, 이미지 문제 ${nImg}개 제외` : ""}`;
  children.push(new Paragraph({
    spacing: { after: 60 },
    bullet: { level: 0 },
    children: [new TextRun({ text: label, font: FONT, size: 21 })],
  }));
}

// ---- 회차별 본문 ----
const langTagMap = { "Python": "Python", "Java": "Java", "C": "C" };

for (const r of rounds) {
  children.push(new Paragraph({
    heading: HeadingLevel.HEADING_1,
    pageBreakBefore: true,
    spacing: { after: 160 },
    children: [new TextRun({ text: `${r.year}년 ${r.round}회 실기 복원문제`, font: FONT, bold: true })],
  }));

  children.push(new Paragraph({
    spacing: { after: 60 },
    children: [
      new TextRun({ text: "원문: ", bold: true, font: FONT, size: 20 }),
      new ExternalHyperlink({
        link: r.source_url,
        children: [new TextRun({ text: r.source_url, style: "Hyperlink", font: FONT, size: 20 })],
      }),
    ],
  }));
  children.push(labelLine("저작자/라이선스:", `${r.source_author} · ${r.license}`));

  const imgList = r.image_only_questions || [];
  if (imgList.length) {
    children.push(new Paragraph({
      spacing: { after: 200 },
      children: [new TextRun({ text: `⚠ ${imgList.join(", ")}번 문제는 원문이 표/다이어그램 이미지로만 제공되어 이 문서에서는 제외했습니다. 원문 링크에서 직접 확인하세요.`, color: "B00000", font: FONT, size: 20 })],
    }));
  } else {
    children.push(new Paragraph({ spacing: { after: 200 }, children: [] }));
  }

  for (const q of r.questions) {
    const lang = (!q.language || q.language === "기타") ? "이론" : q.language;   // 원본의 '기타' → 문서에서는 '이론'
    const diff = q.difficulty ? ` · 난이도 ${q.difficulty}` : "";
    children.push(new Paragraph({
      heading: HeadingLevel.HEADING_2,
      keepNext: true,
      spacing: { after: 100 },
      children: [new TextRun({ text: `${r.year}-${r.round} 문제 ${q.number} (${lang}${diff})`, font: FONT, bold: true, size: 23 })],
    }));
    const fkey = `${r.year}-${r.round}#${q.number}`;
    const fblocks = FORMATTED[fkey];
    if (!fblocks) throw new Error("formatted prompt missing: " + fkey);
    const ctable = CTABLES[fkey];
    children.push(...promptBlocks(fblocks, !!ctable));

    const code = (q.code || "").replace(/\n+$/,'');
    if (ctable) {
      children.push(...tableBlock(ctable, null));          // code 칸에 들어 있던 파이프 표 → 진짜 표
    } else if (code.trim()) {
      children.push(...codeBlock(code));
    }

    children.push(labelLine("정답:", q.answer || ""));

    const expl = (q.explanation || "").trim();
    if (expl) {
      const el = EXPL[fkey] || [expl];
      if (el.length <= 1) {
        children.push(labelLine("해설:", el[0] || expl));
      } else {           // 항목별로 줄을 나눈 해설: 라벨 문단 + 항목마다 한 문단
        children.push(new Paragraph({
          spacing: { after: 20 }, keepNext: true,
          children: [new TextRun({ text: "해설:", bold: true, font: FONT, size: 21 })],
        }));
        el.forEach((t, k) => children.push(new Paragraph({
          spacing: { after: k === el.length - 1 ? 100 : 20 },
          indent: { left: convertInchesToTwip(0.25) },
          children: [new TextRun({ text: t, font: FONT, size: 21 })],
        })));
      }
    }
    children.push(new Paragraph({ spacing: { after: 160 }, border: { bottom: { style: BorderStyle.SINGLE, size: 2, color: "DDDDDD" } }, children: [] }));
  }
}

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: FONT, size: 21 } },
    },
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 }, // A4
        margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "정보처리기사 실기 복원문제 모음 (2020-2026)", size: 16, color: "999999", font: FONT })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "999999" })],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT_PATH, buf);
  console.log("OK:", OUT_PATH, buf.length, "bytes,", children.length, "paragraphs");
});
