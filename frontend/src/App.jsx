import { useEffect, useState } from "react";

const TABS = {
  usage: "usage",
  books: "books"
};
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001").replace(/\/$/, "");

function buildApiUrl(path) {
  return `${API_BASE_URL}${path}`;
}

function StatCard({ label, value, helper }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {helper ? <div className="stat-helper">{helper}</div> : null}
    </div>
  );
}

function SectionHeader({ title, description, action }) {
  return (
    <div className="section-header">
      <div>
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

function formatNumber(value) {
  return new Intl.NumberFormat("zh-CN").format(value || 0);
}

function formatDate(value) {
  return value ? new Date(value.replace(" ", "T")).toLocaleString("zh-CN") : "-";
}

function UsageView() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadUsage = async () => {
    try {
      setLoading(true);
      setError("");
      const response = await fetch(buildApiUrl("/admin/api/usage"));
      const json = await response.json();
      if (!response.ok) {
        throw new Error(json.error || "加载模型用量失败");
      }
      setData(json);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsage();
  }, []);

  if (loading) {
    return <div className="panel-empty">正在加载模型用量...</div>;
  }

  if (error) {
    return <div className="panel-empty panel-error">{error}</div>;
  }

  return (
    <div className="panel-stack">
      <SectionHeader
        title="模型用量总览"
        description="统计每个平台、每个模型以及全局 token 使用情况。"
        action={
          <button className="ghost-button" onClick={loadUsage}>
            刷新
          </button>
        }
      />

      <div className="stats-grid">
        <StatCard label="总请求数" value={formatNumber(data.totals.request_count)} />
        <StatCard label="总输入 Token" value={formatNumber(data.totals.input_tokens)} />
        <StatCard label="总输出 Token" value={formatNumber(data.totals.output_tokens)} />
        <StatCard label="总 Token" value={formatNumber(data.totals.total_tokens)} helper={`最近调用: ${formatDate(data.totals.last_used_at)}`} />
      </div>

      <div className="card">
        <h3>按平台汇总</h3>
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>平台</th>
                <th>请求数</th>
                <th>输入 Token</th>
                <th>输出 Token</th>
                <th>总 Token</th>
                <th>推理 Token</th>
                <th>最近调用</th>
              </tr>
            </thead>
            <tbody>
              {data.providers.map((item) => (
                <tr key={item.provider}>
                  <td>{item.provider}</td>
                  <td>{formatNumber(item.request_count)}</td>
                  <td>{formatNumber(item.input_tokens)}</td>
                  <td>{formatNumber(item.output_tokens)}</td>
                  <td>{formatNumber(item.total_tokens)}</td>
                  <td>{formatNumber(item.reasoning_tokens)}</td>
                  <td>{formatDate(item.last_used_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3>按模型汇总</h3>
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>平台</th>
                <th>模型</th>
                <th>请求数</th>
                <th>输入 Token</th>
                <th>输出 Token</th>
                <th>总 Token</th>
                <th>推理 Token</th>
                <th>最近调用</th>
              </tr>
            </thead>
            <tbody>
              {data.models.map((item) => (
                <tr key={`${item.provider}-${item.model}`}>
                  <td>{item.provider}</td>
                  <td>{item.model}</td>
                  <td>{formatNumber(item.request_count)}</td>
                  <td>{formatNumber(item.input_tokens)}</td>
                  <td>{formatNumber(item.output_tokens)}</td>
                  <td>{formatNumber(item.total_tokens)}</td>
                  <td>{formatNumber(item.reasoning_tokens)}</td>
                  <td>{formatDate(item.last_used_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function BooksView() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const loadBooks = async (currentQuery = query, currentPage = page) => {
    try {
      setLoading(true);
      setError("");
      const params = new URLSearchParams();
      params.set("limit", String(pageSize));
      params.set("offset", String((currentPage - 1) * pageSize));
      if (currentQuery) {
        params.set("search", currentQuery);
      }
      const response = await fetch(buildApiUrl(`/admin/api/books?${params.toString()}`));
      const json = await response.json();
      if (!response.ok) {
        throw new Error(json.error || "加载图书失败");
      }
      setData(json);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBooks("", 1);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const onSubmit = (event) => {
    event.preventDefault();
    const nextQuery = search.trim();
    setQuery(nextQuery);
    setPage(1);
    loadBooks(nextQuery, 1);
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.pagination.total / pageSize)) : 1;

  const goToPage = (nextPage) => {
    setPage(nextPage);
    loadBooks(query, nextPage);
  };

  return (
    <div className="panel-stack">
      <SectionHeader
        title="图书数据"
        description="查看数据库中已缓存的图书信息，支持按书名、作者、ISBN、出版社搜索。"
        action={
          <button className="ghost-button" onClick={() => loadBooks(query, page)}>
            刷新
          </button>
        }
      />

      <form className="search-bar" onSubmit={onSubmit}>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="搜索书名 / 作者 / ISBN / 出版社"
        />
        <button type="submit">搜索</button>
      </form>

      {loading ? <div className="panel-empty">正在加载图书数据...</div> : null}
      {error ? <div className="panel-empty panel-error">{error}</div> : null}

      {!loading && !error && data ? (
        <>
          <div className="stats-grid compact">
            <StatCard label="当前结果数" value={formatNumber(data.items.length)} />
            <StatCard label="数据库总数" value={formatNumber(data.pagination.total)} />
          </div>
          <div className="card">
            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>ISBN</th>
                    <th>书名</th>
                    <th>作者</th>
                    <th>出版社</th>
                    <th>出版日期</th>
                    <th>页数</th>
                    <th>语言</th>
                    <th>创建时间</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((book) => (
                    <tr key={book.id}>
                      <td>{book.id}</td>
                      <td className="mono-cell">{book.isbn || "-"}</td>
                      <td className="book-title-cell" title={book.title || ""}>{book.title || "-"}</td>
                      <td title={book.authors || ""}>{book.authors || "-"}</td>
                      <td title={book.publisher || ""}>{book.publisher || "-"}</td>
                      <td>{book.publish_date || "-"}</td>
                      <td>{book.pages || "-"}</td>
                      <td>{book.language || "-"}</td>
                      <td>{formatDate(book.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <div className="pagination-summary">
                第 {page} / {totalPages} 页，共 {formatNumber(data.pagination.total)} 条
              </div>
              <div className="pagination-actions">
                <button className="ghost-button" onClick={() => goToPage(page - 1)} disabled={page <= 1}>
                  上一页
                </button>
                <button className="ghost-button" onClick={() => goToPage(page + 1)} disabled={page >= totalPages}>
                  下一页
                </button>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState(TABS.usage);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-copy">
          <div className="topbar-title">bookcase-management</div>
          <div className="topbar-subtitle">查看模型 token 用量与数据库图书信息</div>
        </div>
        <div className="topbar-meta">Backend Admin</div>
      </header>

      <nav className="tab-bar">
        <button
          className={activeTab === TABS.usage ? "tab active" : "tab"}
          onClick={() => setActiveTab(TABS.usage)}
        >
          模型用量
        </button>
        <button
          className={activeTab === TABS.books ? "tab active" : "tab"}
          onClick={() => setActiveTab(TABS.books)}
        >
          图书数据
        </button>
      </nav>

      <main>{activeTab === TABS.usage ? <UsageView /> : <BooksView />}</main>
    </div>
  );
}
