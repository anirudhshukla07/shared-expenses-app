import React, { useEffect, useState } from 'react';
import { api, clearToken, getToken, login } from './api';

function Login({ onLogin }) {
  const [username, setUsername] = useState('demo');
  const [password, setPassword] = useState('demo12345');
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
    <main className="card narrow">
      <h1>Shared Expenses</h1>
      <p>Login to import expenses and inspect balances.</p>
      <form onSubmit={submit} className="stack">
        <input value={username} onChange={e => setUsername(e.target.value)} placeholder="Username" />
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Password" />
        <button>Login</button>
        {error && <p className="error">{error}</p>}
      </form>
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
    setGroups(data.results || data);
    const first = (data.results || data)[0];
    if (first) setActiveGroup(first.id);
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

  return (
    <main className="page">
      <header className="topbar">
        <div>
          <h1>Shared Expenses App</h1>
          <p>Import messy expenses, review anomalies, then calculate transparent balances.</p>
        </div>
        <button onClick={() => { clearToken(); setAuthed(false); }}>Logout</button>
      </header>

      <section className="grid">
        <div className="card">
          <h2>1. Group</h2>
          <div className="row">
            <select value={activeGroup || ''} onChange={e => setActiveGroup(e.target.value)}>
              <option value="">Choose group</option>
              {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
            <button onClick={createGroup}>Create group</button>
          </div>
          <p className="hint">Run <code>python manage.py seed_demo</code> to create demo users and membership windows.</p>
        </div>

        <div className="card">
          <h2>2. Import CSV/XLSX</h2>
          <form onSubmit={upload} className="stack">
            <input type="file" name="file" accept=".csv,.xlsx,.xlsm" />
            <label>USD → INR rate
              <input name="usd_inr_rate" defaultValue="83.00" />
            </label>
            <button disabled={!activeGroup}>Import</button>
          </form>
          {error && <pre className="error">{error}</pre>}
        </div>

        <div className="card">
          <h2>3. Balances</h2>
          <button onClick={loadBalances} disabled={!activeGroup}>Refresh balances</button>
          {balances && <>
            <h3>Net balance</h3>
            <table><tbody>{Object.entries(balances.balances).map(([name, amount]) => <tr key={name}><td>{name}</td><td>₹{amount}</td></tr>)}</tbody></table>
            <h3>Settlement suggestions</h3>
            <ul>{balances.settlement_suggestions.map((s, i) => <li key={i}>{s.from} pays {s.to} ₹{s.amount_inr}</li>)}</ul>
          </>}
        </div>
      </section>

      {report && <section className="card">
        <h2>Import report</h2>
        <p>Total: {report.total_rows} | Posted: {report.posted_rows} | Review: {report.review_rows} | Skipped: {report.skipped_rows}</p>
        <table>
          <thead><tr><th>Row</th><th>Code</th><th>Severity</th><th>Action</th><th>Status</th><th>Review</th></tr></thead>
          <tbody>
            {report.anomalies.map(a => <tr key={a.id}>
              <td>{a.row_number}</td><td>{a.code}</td><td>{a.severity}</td><td>{a.action_taken}</td><td>{a.status}</td>
              <td>{a.requires_review && a.status === 'PENDING'
                ? <div className="row"><button onClick={() => reviewAnomaly(a.id, 'approve')}>Approve</button><button className="danger" onClick={() => reviewAnomaly(a.id, 'reject')}>Reject</button></div>
                : String(a.requires_review)}</td>
            </tr>)}
          </tbody>
        </table>
      </section>}
    </main>
  );
}

export default App;
