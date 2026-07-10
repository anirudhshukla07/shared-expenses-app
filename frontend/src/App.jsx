import React, { useEffect, useMemo, useState } from 'react';
import { api, clearToken, download, getToken, login } from './api';

const today = new Date().toISOString().slice(0, 10);
const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(Number(value || 0));
const list = payload => payload?.results || payload || [];

function Brand() {
  return <div className="brand"><span className="brand-mark" aria-hidden="true">S</span><span>Settle<span className="brand-accent">.</span></span></div>;
}

function Icon({ name }) {
  const paths = {
    overview: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
    people: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></>,
    ledger: <><path d="M4 2h16v20H4z"/><path d="M8 6h8M8 10h8M8 14h5"/></>,
    review: <><path d="M21 12a9 9 0 1 1-5.3-8.2"/><path d="M21 3v6h-6"/><path d="m9 12 2 2 4-5"/></>
  };
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

function Login({ onLogin }) {
  const [username, setUsername] = useState('demo');
  const [password, setPassword] = useState('demo12345');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault(); setError(''); setBusy(true);
    try { await login(username, password); onLogin(); } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <main className="login-page">
    <div className="noise" />
    <header className="landing-nav"><Brand /><span>Transparent shared spending</span></header>
    <section className="login-hero">
      <div className="hero-copy">
        <span className="kicker">Built for messy real life</span>
        <h1>Shared expenses are complex.<br/><em>We make them clear.</em></h1>
        <p>Import imperfect data, review every uncertain choice, and trace every rupee from source row to final settlement.</p>
        <div className="proof-row"><span>Four split types</span><span>Dated membership</span><span>Auditable balances</span></div>
      </div>
      <form className="login-card" onSubmit={submit}>
        <span className="card-kicker">Partner login</span><h2>Welcome back</h2><p>Use the seeded demo account to explore the workspace.</p>
        <label>Username<input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" /></label>
        <label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" /></label>
        {error && <div className="alert">{error}</div>}
        <button className="button primary wide" disabled={busy}>{busy ? 'Signing in…' : 'Enter workspace →'}</button>
        <small>Demo: demo / demo12345</small>
      </form>
    </section>
  </main>;
}

function Stat({ value, label, tone }) {
  return <div className={`stat ${tone || ''}`}><strong>{value}</strong><span>{label}</span></div>;
}

function Empty({ title, text }) { return <div className="empty-state"><span>○</span><strong>{title}</strong><p>{text}</p></div>; }

function MembershipRow({ membership, onChanged, onDelete }) {
  const [start, setStart] = useState(membership.starts_on);
  const [end, setEnd] = useState(membership.ends_on || '');
  async function save() {
    await api(`/memberships/${membership.id}/`, { method: 'PATCH', body: JSON.stringify({ starts_on: start, ends_on: end || null }) });
    onChanged();
  }
  return <div className="member-row">
    <div className="avatar">{membership.person_name.slice(0, 1)}</div>
    <div className="member-name"><strong>{membership.person_name}</strong><span>{membership.role}</span></div>
    <label>Joined<input type="date" value={start} onChange={e => setStart(e.target.value)} /></label>
    <label>Left<input type="date" value={end} onChange={e => setEnd(e.target.value)} /></label>
    <button className="button quiet" onClick={save}>Save</button>
    <button className="icon-button danger-text" aria-label={`Remove ${membership.person_name}`} onClick={() => onDelete(membership)}>×</button>
  </div>;
}

function ExpenseForm({ groupId, memberships, initial, onSaved, onCancel }) {
  const [date, setDate] = useState(initial?.date || today);
  const [description, setDescription] = useState(initial?.description || '');
  const [payer, setPayer] = useState(String(initial?.paid_by || ''));
  const [amount, setAmount] = useState(initial?.amount_original || '');
  const [currency, setCurrency] = useState(initial?.currency || 'INR');
  const [rate, setRate] = useState(initial?.fx_rate_to_inr || '83.00');
  const [splitType, setSplitType] = useState(initial?.split_type || 'equal');
  const [participants, setParticipants] = useState(() => new Set((initial?.splits || []).map(split => String(split.person))));
  const [values, setValues] = useState(() => Object.fromEntries((initial?.splits || []).map(split => {
    const parsed = splitType === 'percentage' ? parseFloat(split.basis) : splitType === 'share' ? parseFloat(split.basis) : split.amount_owed_inr;
    return [String(split.person), String(Number.isFinite(parsed) ? parsed : split.amount_owed_inr)];
  })));
  const [notes, setNotes] = useState(initial?.notes || '');
  const [error, setError] = useState('');
  const active = useMemo(() => memberships.filter(member => member.starts_on <= date && (!member.ends_on || member.ends_on >= date)), [memberships, date]);

  useEffect(() => {
    if (payer && !active.some(member => String(member.person) === payer)) setPayer('');
    setParticipants(current => new Set([...current].filter(id => active.some(member => String(member.person) === id))));
  }, [date]);

  function toggle(id) { setParticipants(current => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next; }); }
  function allocations() {
    const ids = [...participants];
    if (!ids.length) throw new Error('Choose at least one participant.');
    const totalPaise = Math.round(Number(amount) * Number(currency === 'INR' ? 1 : rate) * 100);
    if (!Number.isFinite(totalPaise) || totalPaise <= 0) throw new Error('Enter a positive amount and exchange rate.');
    let weights;
    if (splitType === 'equal') weights = ids.map(() => 1);
    else weights = ids.map(id => Number(values[id] || 0));
    if (weights.some(value => !Number.isFinite(value) || value < 0) || weights.reduce((a, b) => a + b, 0) <= 0) throw new Error('Enter valid split values.');
    if (splitType === 'percentage' && Math.abs(weights.reduce((a, b) => a + b, 0) - 100) > 0.001) throw new Error('Percentages must total 100.');
    if (splitType === 'unequal') {
      const allocated = Math.round(weights.reduce((a, b) => a + b, 0) * 100);
      if (allocated !== totalPaise) throw new Error(`Unequal amounts must total ${money(totalPaise / 100)}.`);
      return ids.map((id, index) => ({ person: Number(id), amount_owed_inr: (weights[index]).toFixed(2), basis: 'Manual unequal amount' }));
    }
    const weightTotal = weights.reduce((a, b) => a + b, 0); let used = 0;
    return ids.map((id, index) => {
      const paise = index === ids.length - 1 ? totalPaise - used : Math.round(totalPaise * weights[index] / weightTotal); used += paise;
      const basis = splitType === 'percentage' ? `${weights[index]}%` : splitType === 'share' ? `${weights[index]} shares` : 'Equal split';
      return { person: Number(id), amount_owed_inr: (paise / 100).toFixed(2), basis };
    });
  }
  async function submit(event) {
    event.preventDefault(); setError('');
    try {
      const payload = { group: Number(groupId), date, description, paid_by: Number(payer), amount_original: amount, currency, fx_rate_to_inr: currency === 'INR' ? '1' : rate, split_type: splitType, notes, split_with_raw: active.filter(m => participants.has(String(m.person))).map(m => m.person_name).join('; '), split_details_raw: '', splits: allocations() };
      await api(initial ? `/expenses/${initial.id}/` : '/expenses/', { method: initial ? 'PUT' : 'POST', body: JSON.stringify(payload) });
      onSaved();
    } catch (err) { setError(err.message); }
  }
  return <form className="form-grid expense-form" onSubmit={submit}>
    <label>Date<input type="date" value={date} onChange={e => setDate(e.target.value)} required /></label>
    <label className="span-2">Description<input value={description} onChange={e => setDescription(e.target.value)} placeholder="Rent, dinner, Wi-Fi…" required /></label>
    <label>Paid by<select value={payer} onChange={e => setPayer(e.target.value)} required><option value="">Choose</option>{active.map(member => <option key={member.id} value={member.person}>{member.person_name}</option>)}</select></label>
    <label>Amount<input type="number" min="0.01" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} required /></label>
    <label>Currency<select value={currency} onChange={e => setCurrency(e.target.value)}><option>INR</option><option>USD</option></select></label>
    {currency === 'USD' && <label>₹ per USD<input type="number" min="0.0001" step="0.0001" value={rate} onChange={e => setRate(e.target.value)} /></label>}
    <label>Split method<select value={splitType} onChange={e => setSplitType(e.target.value)}><option value="equal">Equal</option><option value="unequal">Unequal amounts</option><option value="percentage">Percentage</option><option value="share">Shares</option></select></label>
    <fieldset className="participant-field span-all"><legend>Participants active on {date}</legend><div className="participant-grid">{active.map(member => { const id = String(member.person); return <label className={`participant ${participants.has(id) ? 'selected' : ''}`} key={member.id}><input type="checkbox" checked={participants.has(id)} onChange={() => toggle(id)} /><span className="mini-avatar">{member.person_name[0]}</span><strong>{member.person_name}</strong>{splitType !== 'equal' && participants.has(id) && <input className="split-value" type="number" min="0" step="0.01" value={values[id] || ''} placeholder={splitType === 'percentage' ? '%' : splitType === 'share' ? 'shares' : '₹'} onChange={e => setValues({...values, [id]: e.target.value})} onClick={e => e.stopPropagation()} />}</label>; })}</div></fieldset>
    <label className="span-all">Notes<input value={notes} onChange={e => setNotes(e.target.value)} placeholder="Optional context" /></label>
    {error && <div className="alert span-all">{error}</div>}
    <div className="form-actions span-all">{onCancel && <button type="button" className="button secondary" onClick={onCancel}>Cancel</button>}<button className="button primary">{initial ? 'Save changes' : 'Add expense'}</button></div>
  </form>;
}

function SettlementForm({ groupId, memberships, onSaved }) {
  const [form, setForm] = useState({ date: today, paid_by: '', paid_to: '', amount_original: '', notes: '' });
  const active = memberships.filter(member => member.starts_on <= form.date && (!member.ends_on || member.ends_on >= form.date));
  async function submit(event) {
    event.preventDefault();
    await api('/settlements/', { method: 'POST', body: JSON.stringify({ ...form, group: Number(groupId), paid_by: Number(form.paid_by), paid_to: Number(form.paid_to), currency: 'INR', fx_rate_to_inr: '1' }) });
    setForm({ date: today, paid_by: '', paid_to: '', amount_original: '', notes: '' }); onSaved();
  }
  const update = (key, value) => setForm({ ...form, [key]: value });
  return <form className="settlement-form" onSubmit={submit}><input type="date" value={form.date} onChange={e => update('date', e.target.value)} required /><select value={form.paid_by} onChange={e => update('paid_by', e.target.value)} required><option value="">Who paid?</option>{active.map(m => <option key={m.id} value={m.person}>{m.person_name}</option>)}</select><span>paid</span><select value={form.paid_to} onChange={e => update('paid_to', e.target.value)} required><option value="">Who received?</option>{active.map(m => <option key={m.id} value={m.person}>{m.person_name}</option>)}</select><input type="number" min="0.01" step="0.01" placeholder="₹ Amount" value={form.amount_original} onChange={e => update('amount_original', e.target.value)} required /><input placeholder="Note (optional)" value={form.notes} onChange={e => update('notes', e.target.value)} /><button className="button primary">Record</button></form>;
}

function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()));
  const [tab, setTab] = useState('overview');
  const [groups, setGroups] = useState([]); const [activeGroup, setActiveGroup] = useState('');
  const [memberships, setMemberships] = useState([]); const [expenses, setExpenses] = useState([]); const [settlements, setSettlements] = useState([]);
  const [balances, setBalances] = useState(null); const [report, setReport] = useState(null); const [error, setError] = useState('');
  const [editingExpense, setEditingExpense] = useState(null); const [busy, setBusy] = useState(false);

  useEffect(() => { if (authed) loadGroups(); }, [authed]);
  useEffect(() => { if (authed && activeGroup) loadWorkspace(activeGroup); }, [authed, activeGroup]);
  async function loadGroups(selectNewest = false) {
    try { const loaded = list(await api('/groups/')); setGroups(loaded); if (loaded.length && (!activeGroup || selectNewest)) setActiveGroup(String(selectNewest ? loaded.at(-1).id : loaded[0].id)); } catch (err) { setError(err.message); }
  }
  async function loadWorkspace(groupId = activeGroup) {
    setBusy(true); setError('');
    try {
      const [memberData, expenseData, settlementData, balanceData, importData] = await Promise.all([api(`/memberships/?group=${groupId}`), api(`/expenses/?group=${groupId}`), api(`/settlements/?group=${groupId}`), api(`/groups/${groupId}/balances/`), api('/imports/')]);
      setMemberships(list(memberData)); setExpenses(list(expenseData)); setSettlements(list(settlementData)); setBalances(balanceData);
      setReport(list(importData).find(item => String(item.group) === String(groupId)) || null);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  async function createGroup(event) { event.preventDefault(); const name = event.currentTarget.elements.name.value.trim(); if (!name) return; const created = await api('/groups/', { method: 'POST', body: JSON.stringify({ name }) }); event.currentTarget.reset(); await loadGroups(); setActiveGroup(String(created.id)); }
  async function addMember(event) { event.preventDefault(); const data = new FormData(event.currentTarget); await api('/memberships/', { method: 'POST', body: JSON.stringify({ group: Number(activeGroup), person_name_input: data.get('name'), starts_on: data.get('starts_on'), ends_on: data.get('ends_on') || null, role: 'member' }) }); event.currentTarget.reset(); await loadWorkspace(); }
  async function removeMembership(member) { if (!confirm(`Remove ${member.person_name} from this group? Existing ledger entries are preserved.`)) return; await api(`/memberships/${member.id}/`, { method: 'DELETE' }); await loadWorkspace(); }
  async function removeExpense(expense) { if (!confirm(`Delete “${expense.description}”?`)) return; await api(`/expenses/${expense.id}/`, { method: 'DELETE' }); await loadWorkspace(); }
  async function removeSettlement(item) { if (!confirm('Delete this payment?')) return; await api(`/settlements/${item.id}/`, { method: 'DELETE' }); await loadWorkspace(); }
  async function upload(event) { event.preventDefault(); const file = event.currentTarget.elements.file.files[0]; if (!file) return; const body = new FormData(); body.append('file', file); body.append('usd_inr_rate', event.currentTarget.elements.rate.value || '83'); body.append('replace_existing', event.currentTarget.elements.mode.value === 'replace' ? 'true' : 'false'); setBusy(true); try { setReport(await api(`/groups/${activeGroup}/import/`, { method: 'POST', body })); await loadWorkspace(); setTab('review'); } catch (err) { setError(err.message); } finally { setBusy(false); } }
  async function decide(anomaly, decision) { try { await api(`/anomalies/${anomaly.id}/${decision}/`, { method: 'POST' }); await loadWorkspace(); } catch (err) { setError(err.message); } }
  function logout() { clearToken(); setAuthed(false); }
  if (!authed) return <Login onLogin={() => setAuthed(true)} />;

  const selectedGroup = groups.find(group => String(group.id) === String(activeGroup));
  const pending = report?.pending_review_rows ?? 0;
  const reportRows = (report?.report_json?.rows || []).map(row => ({ ...row, anomalies: report.anomalies.filter(item => item.row_number === row.row_number) }));
  const totalSpend = expenses.filter(item => item.status === 'POSTED').reduce((sum, item) => sum + Number(item.amount_inr), 0);
  const nav = [{id:'overview',label:'Overview',icon:'overview'},{id:'members',label:'Members',icon:'people'},{id:'ledger',label:'Expenses',icon:'ledger'},{id:'review',label:'Import review',icon:'review',badge:pending}];

  return <div className="app-shell">
    <header className="app-header"><Brand/><nav>{nav.map(item => <button key={item.id} className={tab === item.id ? 'active' : ''} onClick={() => setTab(item.id)}><Icon name={item.icon}/>{item.label}{item.badge > 0 && <b>{item.badge}</b>}</button>)}</nav><div className="header-actions"><select value={activeGroup} onChange={e => setActiveGroup(e.target.value)}><option value="">Choose group</option>{groups.map(group => <option key={group.id} value={group.id}>{group.name}</option>)}</select><button className="button outline" onClick={logout}>Log out</button></div></header>
    <main className="workspace">
      <div className="page-heading"><div><span className="kicker">{selectedGroup?.name || 'Shared expenses'}</span><h1>{tab === 'overview' ? 'Every rupee, explained.' : nav.find(item => item.id === tab)?.label}</h1><p>{tab === 'overview' ? 'A clean view of what happened, what needs attention, and who should pay whom.' : 'Manage the ledger with decisions that remain visible and auditable.'}</p></div><span className={`live-status ${busy ? 'working' : ''}`}><i/>{busy ? 'Updating…' : 'Ledger up to date'}</span></div>
      {error && <div className="alert global-alert">{error}<button onClick={() => setError('')}>×</button></div>}
      {!groups.length && <section className="hero-empty"><h2>Create your first expense group</h2><p>Groups keep memberships, imports, expenses, and balances separate.</p><form onSubmit={createGroup}><input name="name" placeholder="Flat 4B · 2026" required/><button className="button primary">Create group</button></form></section>}
      {selectedGroup && tab === 'overview' && <>
        <section className="stats"><Stat value={money(totalSpend)} label="Posted group spend"/><Stat value={expenses.length} label="Expense records"/><Stat value={memberships.length} label="Membership periods"/><Stat value={pending} label="Rows need a decision" tone={pending ? 'warning' : 'good'}/></section>
        <section className="dashboard-grid"><div className="surface balance-surface"><div className="surface-heading"><div><span className="kicker">Position</span><h2>Group balances</h2></div><button className="button quiet" onClick={() => loadWorkspace()}>Refresh</button></div>{balances && Object.keys(balances.breakdown || {}).length ? <div className="balance-cards">{Object.entries(balances.breakdown).map(([name, detail]) => <details key={name} className="balance-card"><summary><span className="avatar">{name[0]}</span><span><strong>{name}</strong><small>{Number(detail.net_inr) >= 0 ? 'gets back' : 'owes'}</small></span><b className={Number(detail.net_inr) >= 0 ? 'credit' : 'debt'}>{money(Math.abs(detail.net_inr))}</b><i>⌄</i></summary><div className="trace"><div className="trace-total"><span>Calculation trace</span><strong>{money(detail.net_inr)}</strong></div>{detail.entries.map((entry, index) => <div className="trace-row" key={`${entry.kind}-${entry.expense_id || entry.settlement_id}-${index}`}><span><strong>{entry.description}</strong><small>{entry.date} · {entry.explanation}</small></span><b className={Number(entry.amount_inr) >= 0 ? 'credit' : 'debt'}>{Number(entry.amount_inr) >= 0 ? '+' : ''}{money(entry.amount_inr)}</b></div>)}</div></details>)}</div> : <Empty title="No posted activity" text="Add an expense or import a ledger to calculate balances."/>}</div>
        <aside className="surface settlement-surface"><div className="surface-heading"><div><span className="kicker">Simplest path</span><h2>Settle up</h2></div></div><div className="suggestions">{balances?.settlement_suggestions?.length ? balances.settlement_suggestions.map((item,index) => <div className="suggestion" key={index}><div><span className="avatar">{item.from[0]}</span><span><strong>{item.from}</strong><small>pays {item.to}</small></span></div><b>{money(item.amount_inr)}</b></div>) : <Empty title="All square" text="No repayments are needed right now."/>}</div><button className="button primary wide" onClick={() => setTab('ledger')}>Record a payment</button></aside></section>
        <section className="surface recent"><div className="surface-heading"><div><span className="kicker">Recent ledger</span><h2>Latest activity</h2></div><button className="text-button" onClick={() => setTab('ledger')}>View all →</button></div><div className="ledger-list">{[...expenses].reverse().slice(0,5).map(item => <div className="ledger-row" key={item.id}><span className="expense-glyph">{item.description[0]}</span><span><strong>{item.description}</strong><small>{item.date} · Paid by {item.paid_by_name} · {item.split_type}</small></span><b>{money(item.amount_inr)}</b><em className={`row-status ${item.status.toLowerCase()}`}>{item.status.replace('_',' ')}</em></div>)}</div></section>
      </>}
      {selectedGroup && tab === 'members' && <section className="two-column"><div className="surface"><div className="surface-heading"><div><span className="kicker">Time-aware access</span><h2>Membership periods</h2></div></div><p className="surface-intro">Dates control who can be included in an expense. A person can have more than one membership period.</p><div className="member-list">{memberships.map(member => <MembershipRow key={member.id} membership={member} onChanged={loadWorkspace} onDelete={removeMembership}/>)}</div></div><aside className="surface sticky-card"><span className="kicker">Add someone</span><h2>New membership</h2><form className="stack-form" onSubmit={addMember}><label>Name<input name="name" placeholder="Member name" required /></label><label>Joins on<input name="starts_on" type="date" required /></label><label>Leaves on <small>optional</small><input name="ends_on" type="date" /></label><button className="button primary wide">Add member</button></form><hr/><span className="kicker">Groups</span><form className="stack-form compact" onSubmit={createGroup}><input name="name" placeholder="New group name" required/><button className="button secondary wide">Create another group</button></form></aside></section>}
      {selectedGroup && tab === 'ledger' && <><section className="surface editor"><div className="surface-heading"><div><span className="kicker">{editingExpense ? 'Editing record' : 'New record'}</span><h2>{editingExpense ? editingExpense.description : 'Add an expense'}</h2></div></div><ExpenseForm groupId={activeGroup} memberships={memberships} initial={editingExpense} onCancel={editingExpense ? () => setEditingExpense(null) : null} onSaved={async () => { setEditingExpense(null); await loadWorkspace(); }}/></section><section className="surface"><div className="surface-heading"><div><span className="kicker">Expense ledger</span><h2>{expenses.length} records</h2></div></div><div className="ledger-list detailed">{expenses.length ? [...expenses].reverse().map(item => <div className="ledger-row" key={item.id}><span className="expense-glyph">{item.description[0]}</span><span><strong>{item.description}</strong><small>{item.date} · {item.paid_by_name} paid {item.currency === 'USD' ? `$${item.amount_original} × ₹${item.fx_rate_to_inr} = ` : ''}{money(item.amount_inr)} · {item.split_type}</small><small>{item.splits.map(split => `${split.person_name} ${money(split.amount_owed_inr)}`).join(' · ')}</small></span><b>{money(item.amount_inr)}</b><em className={`row-status ${item.status.toLowerCase()}`}>{item.status.replace('_',' ')}</em><div className="row-actions"><button className="text-button" onClick={() => { setEditingExpense(item); window.scrollTo({top:0,behavior:'smooth'}); }}>Edit</button><button className="text-button danger-text" onClick={() => removeExpense(item)}>Delete</button></div></div>) : <Empty title="No expenses yet" text="Use the form above or import the source CSV."/>}</div></section><section className="surface payment-panel"><div className="surface-heading"><div><span className="kicker">Repayments</span><h2>Record a payment</h2></div></div><SettlementForm groupId={activeGroup} memberships={memberships} onSaved={loadWorkspace}/><div className="payment-list">{[...settlements].reverse().map(item => <div key={item.id}><span><strong>{item.paid_by_name}</strong> paid {item.paid_to_name}<small>{item.date}{item.notes ? ` · ${item.notes}` : ''}</small></span><b>{money(item.amount_inr)}</b><button className="icon-button danger-text" onClick={() => removeSettlement(item)}>×</button></div>)}</div></section></>}
      {selectedGroup && tab === 'review' && <><section className="surface import-panel"><div><span className="kicker">Source data</span><h2>Import without cleaning</h2><p>CSV is mandatory; XLSX is supported too. Every source row ends as Posted, Needs review, or Skipped.</p></div><form onSubmit={upload}><label>Expense export<input type="file" name="file" accept=".csv,.xlsx,.xlsm" required/></label><label>USD → INR rate<input name="rate" type="number" defaultValue="83" min="0.0001" step="0.0001"/></label><label>Import mode<select name="mode"><option value="replace">Replace earlier imported rows</option><option value="append">Append, blocking exact re-imports</option></select></label><button className="button primary" disabled={busy}>{busy ? 'Inspecting…' : 'Import & inspect'}</button></form></section>{report ? <section className="surface report"><div className="surface-heading report-heading"><div><span className="kicker">Batch #{report.id} · {report.source_filename}</span><h2>Row-level import report</h2><p>{report.processed_rows} of {report.total_rows} rows accounted for · {report.counts_are_consistent ? 'consistency check passed' : 'count mismatch'}</p></div><div className="download-actions"><button className="button secondary" onClick={() => download(`/imports/${report.id}/report/?export=csv`, `import-${report.id}-report.csv`)}>Download CSV</button><button className="button outline" onClick={() => download(`/imports/${report.id}/report/?export=json`, `import-${report.id}-report.json`)}>JSON</button></div></div><section className="report-stats"><Stat value={report.total_rows} label="Source rows"/><Stat value={report.posted_rows} label="Posted" tone="good"/><Stat value={report.review_rows} label="Needs review" tone="warning"/><Stat value={report.skipped_rows} label="Skipped"/></section><div className="table-wrap"><table><thead><tr><th>CSV row</th><th>Detected problem & reason</th><th>Documented action</th><th>Final status</th><th>Decision</th></tr></thead><tbody>{reportRows.map(row => { const pendingAnomaly = row.anomalies.find(a => a.requires_review && a.status === 'PENDING'); return <tr key={row.row_number}><td><b>#{row.row_number}</b></td><td>{row.anomalies.length ? row.anomalies.map(a => <div className="anomaly" key={a.id}><span className={`severity ${a.severity.toLowerCase()}`}>{a.severity}</span><span><strong>{a.code.replaceAll('_',' ')}</strong><small>{a.message}</small><small className="policy">Policy: {a.policy}</small></span></div>) : <span className="muted">No anomaly detected</span>}</td><td>{row.anomalies.length ? row.anomalies.map(a => <p key={a.id}>{a.action_taken}</p>) : 'Posted as supplied'}</td><td><em className={`row-status ${String(row.status).toLowerCase()}`}>{String(row.status).replace('_',' ')}</em></td><td>{pendingAnomaly ? <div className="decision-actions"><button className="button approve" onClick={() => decide(pendingAnomaly,'approve')}>Approve row</button><button className="button reject" onClick={() => decide(pendingAnomaly,'reject')}>Reject</button></div> : <span className="muted">{row.anomalies.some(a => a.status === 'APPROVED') ? 'Approved' : row.anomalies.some(a => a.status === 'REJECTED') ? 'Rejected' : 'No decision needed'}</span>}</td></tr>; })}</tbody></table></div></section> : <Empty title="No import yet" text="Upload the original CSV unchanged to produce the audit report."/>}</>}
    </main>
  </div>;
}

export default App;
