import React, { useEffect, useState } from 'react';
import { api, clearToken, getToken, login } from './api';

const formatMoney = value => {
  const number = Number(value || 0);
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2
  }).format(Number.isFinite(number) ? number : 0);
};

function Metric({ label, value, tone = 'default' }) {
  return (
    <div className={`metric metric-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  async function submit(e) {
    e.preventDefault();
    setError('');
    try {
      await login(username, password);
      onLogin();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="login-page">
      <span className="login-dot login-dot-left" />
      <span className="login-dot login-dot-right" />
      <section className="login-panel">
        <div className="money-mark" aria-hidden="true">💰</div>
        <h1>Welcome Back</h1>
        <div className="login-rule" />
        <p>Sign in to your Expense Tracker</p>
        <form onSubmit={submit} className="login-form">
          <label>
            Username
            <input value={username} onChange={e => setUsername(e.target.value)} placeholder="Enter your username" />
          </label>
          <label className="password-field">
            Password
            <span className="password-control">
              <input type={showPassword ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter your password" />
              <button type="button" className="eye-button" aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword(value => !value)}>
                <span className={showPassword ? 'eye-icon eye-open' : 'eye-icon'} />
              </button>
            </span>
          </label>
          <button className="primary login-submit">Sign In <span aria-hidden="true">→</span></button>
          {error && <p className="error">{error}</p>}
        </form>
      </section>
    </main>
  );
}

function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()));
  const [groups, setGroups] = useState([]);
  const [activeGroup, setActiveGroup] = useState(null);
  const [report, setReport] = useState(null);
  const [balances, setBalances] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (authed) loadGroups();
  }, [authed]);

  async function loadGroups() {
    const data = await api('/groups/');
    const loadedGroups = data.results || data;
    setGroups(loadedGroups);
    const first = loadedGroups[0];
    if (first && !activeGroup) setActiveGroup(first.id);
  }

  async function createGroup() {
    const name = prompt('Group name?', 'Flatmates Feb-Apr 2026');
    if (!name) return;
    await api('/groups/', { method: 'POST', body: JSON.stringify({ name }) });
    await loadGroups();
  }

  async function upload(e) {
    e.preventDefault();
    setError('');
    const file = e.target.elements.file.files[0];
    if (!file || !activeGroup) return;
    const form = new FormData();
    form.append('file', file);
    form.append('usd_inr_rate', e.target.elements.usd_inr_rate.value || '83.00');
    try {
      const data = await api(`/groups/${activeGroup}/import/`, { method: 'POST', body: form, headers: {} });
      setReport(data);
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadBalances() {
    if (!activeGroup) return;
    const data = await api(`/groups/${activeGroup}/balances/`);
    setBalances(data);
  }

  async function reviewAnomaly(id, decision) {
    setError('');
    try {
      await api(`/anomalies/${id}/${decision}/`, { method: 'POST' });
      const updated = await api(`/imports/${report.id}/`);
      setReport(updated);
      await loadBalances();
    } catch (err) {
      setError(err.message);
    }
  }

  if (!authed) return <Login onLogin={() => setAuthed(true)} />;

  const selectedGroup = groups.find(group => String(group.id) === String(activeGroup));
  const pendingCount = report?.anomalies?.filter(a => a.requires_review && a.status === 'PENDING').length || 0;

  return (
    <main className="page">
      <header className="topbar">
        <div>
          <span className="eyebrow">Expense review workspace</span>
          <h1>Shared Expenses</h1>
          <p>Import messy flatmate expenses, review anomalies, and calculate transparent balances.</p>
        </div>
        <button className="ghost" onClick={() => { clearToken(); setAuthed(false); }}>Logout</button>
      </header>

      <section className="summary-strip" aria-label="Current workspace summary">
        <Metric label="Active group" value={selectedGroup?.name || 'Not selected'} />
        <Metric label="Rows posted" value={report?.posted_rows ?? '-'} tone="green" />
        <Metric label="Needs review" value={pendingCount} tone="amber" />
        <Metric label="Skipped rows" value={report?.skipped_rows ?? '-'} tone="red" />
      </section>

      <section className="workflow-grid">
        <div className="panel">
          <div className="panel-heading">
            <span className="step">01</span>
            <div>
              <h2>Choose group</h2>
              <p>Select the ledger you want to import into.</p>
            </div>
          </div>
          <div className="split-row">
            <select value={activeGroup || ''} onChange={e => setActiveGroup(e.target.value)}>
              <option value="">Choose group</option>
              {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
            <button className="secondary" onClick={createGroup}>Create</button>
          </div>
          <p className="hint">Run <code>python manage.py seed_demo</code> to create demo users and membership windows.</p>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <span className="step">02</span>
            <div>
              <h2>Import CSV/XLSX</h2>
              <p>Upload an expense export and pick the USD conversion rate.</p>
            </div>
          </div>
          <form onSubmit={upload} className="stack">
            <label>
              Expense file
              <input type="file" name="file" accept=".csv,.xlsx,.xlsm" />
            </label>
            <label>
              USD to INR rate
              <input name="usd_inr_rate" defaultValue="83.00" />
            </label>
            <button className="primary" disabled={!activeGroup}>Import file</button>
          </form>
          {error && <pre className="error">{error}</pre>}
        </div>

        <div className="panel">
          <div className="panel-heading">
            <span className="step">03</span>
            <div>
              <h2>Balances</h2>
              <p>Refresh after imports or anomaly decisions.</p>
            </div>
          </div>
          <button className="primary full" onClick={loadBalances} disabled={!activeGroup}>Refresh balances</button>
          {balances && <>
            <div className="section-title">Net balance</div>
            <div className="balance-list">
              {Object.entries(balances.balances).map(([name, amount]) => (
                <div className="balance-row" key={name}>
                  <span>{name}</span>
                  <strong className={Number(amount) >= 0 ? 'positive' : 'negative'}>{formatMoney(amount)}</strong>
                </div>
              ))}
            </div>
            <div className="section-title">Settlement suggestions</div>
            <div className="settlements">
              {balances.settlement_suggestions.length
                ? balances.settlement_suggestions.map((s, i) => <p key={i}>{s.from} pays {s.to} <strong>{formatMoney(s.amount_inr)}</strong></p>)
                : <p className="empty">No settlements needed.</p>}
            </div>
          </>}
        </div>
      </section>

      {report && <section className="report-panel">
        <div className="report-header">
          <div>
            <span className="eyebrow">Import batch #{report.id}</span>
            <h2>Import report</h2>
          </div>
          <div className="report-metrics">
            <Metric label="Total" value={report.total_rows} />
            <Metric label="Posted" value={report.posted_rows} tone="green" />
            <Metric label="Review" value={report.review_rows} tone="amber" />
            <Metric label="Skipped" value={report.skipped_rows} tone="red" />
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Row</th><th>Code</th><th>Severity</th><th>Action</th><th>Status</th><th>Review</th></tr></thead>
            <tbody>
              {report.anomalies.map(a => <tr key={a.id}>
                <td>{a.row_number}</td>
                <td><span className="code-pill">{a.code}</span></td>
                <td><span className={`severity severity-${String(a.severity).toLowerCase()}`}>{a.severity}</span></td>
                <td>{a.action_taken}</td>
                <td><span className="status">{a.status}</span></td>
                <td>{a.requires_review && a.status === 'PENDING'
                  ? <div className="actions"><button className="secondary" onClick={() => reviewAnomaly(a.id, 'approve')}>Approve</button><button className="danger" onClick={() => reviewAnomaly(a.id, 'reject')}>Reject</button></div>
                  : <span className="muted">{a.requires_review ? 'Reviewed' : 'No review'}</span>}</td>
              </tr>)}
            </tbody>
          </table>
        </div>
      </section>}
    </main>
  );
}

export default App;
