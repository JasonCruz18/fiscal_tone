import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import "./App.css";

type CorpusStats = {
  corpus_overview: {
    total_paragraphs: number;
    total_documents: number;
    total_characters: number;
    date_generated: string;
  };
  by_year: Record<string, { documents: number; paragraphs: number }>;
  by_document_type: Record<string, { documents: number; paragraphs: number }>;
  by_source_type: Record<string, { documents: number; paragraphs: number }>;
};

type Paragraph = {
  paragraph_num: number;
  text: string;
  length: number;
  page_range: string;
  pdf_filename: string;
  doc_title: string;
  doc_type: string;
  doc_number: number | string;
  date: string;
  year: string | number;
  month: number;
  source_type: string;
  pdf_type?: string;
  pdf_url?: string;
  page_url?: string;
};

type Dataset = {
  stats: CorpusStats | null;
  rawParagraphs: Paragraph[];
  cleanParagraphs: Paragraph[];
};

const NAV_ITEMS = [
  "Overview",
  "Series",
  "Doc Types",
  "Source Types",
  "Cleaning Impact",
  "Paragraphs",
];

function formatNumber(value: number) {
  return value.toLocaleString("en-US");
}

function bucketLengths(data: Paragraph[], binSize = 200) {
  const max = data.reduce((acc, d) => Math.max(acc, d.length), 0);
  const bins = Math.max(1, Math.ceil(max / binSize));
  const counts = Array.from({ length: bins }, () => 0);
  data.forEach((p) => {
    const idx = Math.min(Math.floor(p.length / binSize), bins - 1);
    counts[idx] += 1;
  });
  return counts.map((count, i) => ({
    label: `${i * binSize}-${(i + 1) * binSize}`,
    count,
  }));
}

function uniqueDocuments(paragraphs: Paragraph[]) {
  const map = new Map<string, Paragraph>();
  paragraphs.forEach((p) => {
    if (!map.has(p.pdf_filename)) {
      map.set(p.pdf_filename, p);
    }
  });
  return Array.from(map.values());
}

function Card({
  title,
  value,
  accent,
}: {
  title: string;
  value: string;
  accent?: "primary" | "navy" | "red" | "gold";
}) {
  const color =
    accent === "navy"
      ? "var(--navy)"
      : accent === "red"
      ? "var(--primary-strong)"
      : accent === "gold"
      ? "var(--accent)"
      : "var(--primary)";
  return (
    <div className="card">
      <div className="kpi-title">{title}</div>
      <div className="kpi-value" style={{ color }}>
        {value}
      </div>
    </div>
  );
}

function ChartCard({
  title,
  badge,
  option,
  height = 280,
}: {
  title: string;
  badge?: string;
  option: any;
  height?: number;
}) {
  return (
    <div className="chart-card">
      <div className="card-head">
        <h3>{title}</h3>
        {badge ? <span className="badge">{badge}</span> : null}
      </div>
      <ReactECharts option={option} style={{ height }} />
    </div>
  );
}

function App() {
  const [data, setData] = useState<Dataset>({
    stats: null,
    rawParagraphs: [],
    cleanParagraphs: [],
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [statsRes, rawRes, cleanRes] = await Promise.all([
        fetch("/metadata/corpus_statistics.json"),
        fetch("/metadata/cf_normalized_paragraphs.json"),
        fetch("/metadata/cf_normalized_paragraphs_cleaned.json"),
      ]);
      const stats: CorpusStats = await statsRes.json();
      const rawParagraphs: Paragraph[] = await rawRes.json();
      const cleanParagraphs: Paragraph[] = await cleanRes.json();
      setData({ stats, rawParagraphs, cleanParagraphs });
      setLoading(false);
    }
    load();
  }, []);

  const yearSeries = useMemo(() => {
    if (!data.stats) return [];
    return Object.entries(data.stats.by_year)
      .map(([year, v]) => ({ year, ...v }))
      .sort((a, b) => Number(a.year) - Number(b.year));
  }, [data.stats]);

  const docTypeSeries = useMemo(() => {
    if (!data.stats) return [];
    return Object.entries(data.stats.by_document_type).map(([name, v]) => ({
      name,
      value: v.documents,
    }));
  }, [data.stats]);

  const sourceTypeSeries = useMemo(() => {
    if (!data.stats) return [];
    return Object.entries(data.stats.by_source_type).map(([name, v]) => ({
      name,
      value: v.documents,
    }));
  }, [data.stats]);

  const lengthBucketsRaw = useMemo(
    () => bucketLengths(data.rawParagraphs, 200),
    [data.rawParagraphs]
  );
  const lengthBucketsClean = useMemo(
    () => bucketLengths(data.cleanParagraphs, 200),
    [data.cleanParagraphs]
  );

  const documents = useMemo(
    () => uniqueDocuments(data.rawParagraphs).slice(0, 8),
    [data.rawParagraphs]
  );

  if (loading || !data.stats) {
    return (
      <div className="app">
        <aside className="sidebar">
          <div className="brand">FiscalTone</div>
          <div className="nav">
            {NAV_ITEMS.map((item) => (
              <a key={item}>{item}</a>
            ))}
          </div>
        </aside>
        <main className="content">
          <div className="loading">Loading dashboard data…</div>
        </main>
      </div>
    );
  }

  const { corpus_overview } = data.stats;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">FiscalTone</div>
        <div className="nav">
          {NAV_ITEMS.map((item) => (
            <a key={item}>{item}</a>
          ))}
        </div>
        <div className="status-bar">
          <span className="pill gold">Updated</span>
          <span>{new Date(corpus_overview.date_generated).toLocaleString()}</span>
        </div>
      </aside>

      <main className="content">
        <div className="topbar">
          <h1 className="title">Fiscal Council Dashboard</h1>
          <div className="search">
            <span role="img" aria-label="search">
              🔍
            </span>
            <input placeholder="Search paragraphs or documents (coming soon)" />
          </div>
        </div>

        <div className="cards">
          <Card title="Total Documents" value={formatNumber(corpus_overview.total_documents)} />
          <Card title="Total Paragraphs" value={formatNumber(corpus_overview.total_paragraphs)} accent="navy" />
          <Card title="Total Characters" value={formatNumber(corpus_overview.total_characters)} accent="gold" />
          <Card
            title="Paragraphs/Doc"
            value={(
              corpus_overview.total_paragraphs / corpus_overview.total_documents
            ).toFixed(1)}
            accent="red"
          />
        </div>

        <div className="grid">
          <ChartCard
            title="Documents per Year"
            badge="Series"
            option={{
              backgroundColor: "transparent",
              tooltip: { trigger: "axis" },
              xAxis: {
                type: "category",
                data: yearSeries.map((d) => d.year),
                axisLine: { lineStyle: { color: "#b9a8a2" } },
              },
              yAxis: { type: "value", splitLine: { lineStyle: { color: "#e4d9d2" } } },
              series: [
                {
                  type: "bar",
                  data: yearSeries.map((d) => d.documents),
                  itemStyle: { color: "var(--primary)" },
                  barWidth: 24,
                },
              ],
            }}
          />

          <ChartCard
            title="Paragraphs per Year"
            badge="Series"
            option={{
              backgroundColor: "transparent",
              tooltip: { trigger: "axis" },
              xAxis: {
                type: "category",
                data: yearSeries.map((d) => d.year),
                axisLine: { lineStyle: { color: "#b9a8a2" } },
              },
              yAxis: { type: "value", splitLine: { lineStyle: { color: "#e4d9d2" } } },
              series: [
                {
                  type: "line",
                  smooth: true,
                  data: yearSeries.map((d) => d.paragraphs),
                  lineStyle: { color: "var(--navy)", width: 3 },
                  areaStyle: { color: "rgba(17, 42, 92, 0.08)" },
                  symbol: "circle",
                  symbolSize: 8,
                },
              ],
            }}
          />

          <ChartCard
            title="Document Type Mix"
            badge="Doc Types"
            option={{
              backgroundColor: "transparent",
              tooltip: { trigger: "item" },
              legend: { bottom: 0, textStyle: { color: "#5e524f" } },
              series: [
                {
                  type: "pie",
                  radius: ["45%", "70%"],
                  itemStyle: { borderColor: "#fff", borderWidth: 3 },
                  data: docTypeSeries.map((d, i) => ({
                    ...d,
                    itemStyle: {
                      color: i === 0 ? "var(--primary)" : "var(--navy)",
                    },
                  })),
                  label: { color: "#1f1a19" },
                },
              ],
            }}
          />

          <ChartCard
            title="Source Type (Editable vs Scanned)"
            badge="Source"
            option={{
              backgroundColor: "transparent",
              tooltip: { trigger: "axis" },
              xAxis: { type: "category", data: sourceTypeSeries.map((d) => d.name) },
              yAxis: { type: "value", splitLine: { lineStyle: { color: "#e4d9d2" } } },
              series: [
                {
                  type: "bar",
                  data: sourceTypeSeries.map((d) => d.value),
                  itemStyle: {
                    color: (params: any) =>
                      params.name === "editable" ? "var(--primary)" : "var(--navy)",
                  },
                  barWidth: 36,
                },
              ],
            }}
          />

          <ChartCard
            title="Paragraph Length Distribution (Raw vs Cleaned)"
            badge="Cleaning Impact"
            height={320}
            option={{
              backgroundColor: "transparent",
              tooltip: { trigger: "axis" },
              legend: { top: 0, textStyle: { color: "#5e524f" } },
              xAxis: {
                type: "category",
                data: lengthBucketsRaw.map((d) => d.label),
                axisLabel: { rotate: 45 },
              },
              yAxis: { type: "value", splitLine: { lineStyle: { color: "#e4d9d2" } } },
              series: [
                {
                  name: "Raw",
                  type: "line",
                  data: lengthBucketsRaw.map((d) => d.count),
                  smooth: true,
                  lineStyle: { color: "var(--primary-strong)", width: 3 },
                  areaStyle: { color: "rgba(232, 75, 75, 0.1)" },
                },
                {
                  name: "Cleaned",
                  type: "line",
                  data: lengthBucketsClean.map((d) => d.count),
                  smooth: true,
                  lineStyle: { color: "var(--navy)", width: 3 },
                  areaStyle: { color: "rgba(17, 42, 92, 0.1)" },
                },
              ],
            }}
          />

          <div className="chart-card">
            <div className="card-head">
              <h3>Sample Documents</h3>
              <span className="badge">List</span>
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Type</th>
                  <th>Date</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.pdf_filename}>
                    <td>
                      <div>{doc.doc_title}</div>
                      <div style={{ color: "var(--muted)", fontSize: 12 }}>
                        {doc.pdf_filename}
                      </div>
                    </td>
                    <td>
                      <span className={`pill ${doc.doc_type === "Informe" ? "blue" : "red"}`}>
                        {doc.doc_type}
                      </span>
                    </td>
                    <td>{new Date(doc.date).toLocaleDateString()}</td>
                    <td>
                      <span className={doc.source_type === "editable" ? "pill gold" : "pill blue"}>
                        {doc.source_type}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
