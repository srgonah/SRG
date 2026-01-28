import { useEffect, useState, useCallback } from "react";
import { reminders as api } from "../api/client";
import type { Reminder, CreateReminderRequest } from "../types/api";
import Spinner from "../components/Spinner";
import ErrorBanner from "../components/ErrorBanner";
import Badge from "../components/Badge";
import Modal from "../components/Modal";

type View = "active" | "upcoming" | "all";

const EMPTY_FORM: CreateReminderRequest = {
  title: "",
  message: "",
  due_date: "",
};

export default function Reminders() {
  const [items, setItems] = useState<Reminder[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [view, setView] = useState<View>("active");
  const [modalOpen, setModalOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    const req =
      view === "upcoming"
        ? api.upcoming(7)
        : api.list({ include_done: view === "all", limit: 100 });
    req
      .then((r) => {
        setItems(r.reminders);
        setTotal(r.total);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [view]);

  useEffect(load, [load]);

  const openCreate = () => {
    setEditId(null);
    setForm(EMPTY_FORM);
    setModalOpen(true);
  };

  const openEdit = (r: Reminder) => {
    setEditId(r.id);
    setForm({
      title: r.title,
      message: r.message,
      due_date: r.due_date,
    });
    setModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      if (editId != null) {
        await api.update(editId, {
          title: form.title,
          message: form.message || undefined,
          due_date: form.due_date,
        });
      } else {
        await api.create(form);
      }
      setModalOpen(false);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const toggleDone = async (r: Reminder) => {
    try {
      await api.update(r.id, { is_done: !r.is_done });
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this reminder?")) return;
    try {
      await api.delete(id);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Reminders</h1>
        <button
          onClick={openCreate}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm transition-colors"
        >
          New Reminder
        </button>
      </div>

      {/* View tabs */}
      <div className="flex gap-1 mb-4">
        {(
          [
            ["active", "Active"],
            ["upcoming", "Upcoming 7d"],
            ["all", "All"],
          ] as const
        ).map(([v, label]) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`px-4 py-2 rounded text-sm transition-colors ${
              view === v ? "bg-slate-700 text-white" : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      <p className="text-sm text-slate-500 mb-3">{total} reminder{total !== 1 ? "s" : ""}</p>

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner className="w-8 h-8" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-slate-600 text-center py-12">No reminders found.</p>
      ) : (
        <div className="space-y-3">
          {items.map((r) => (
            <div
              key={r.id}
              className={`bg-slate-900 border rounded-lg p-4 flex items-start justify-between gap-4 ${
                r.is_done
                  ? "border-slate-800 opacity-60"
                  : r.is_overdue
                    ? "border-red-500/30"
                    : "border-slate-800"
              }`}
            >
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <input
                  type="checkbox"
                  checked={r.is_done}
                  onChange={() => toggleDone(r)}
                  className="mt-1 accent-blue-500 shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <h3 className={`font-medium truncate ${r.is_done ? "line-through" : ""}`}>
                      {r.title}
                    </h3>
                    {r.is_overdue && !r.is_done && <Badge color="red">Overdue</Badge>}
                    {r.is_done && <Badge color="green">Done</Badge>}
                  </div>
                  {r.message && <p className="text-sm text-slate-400 mb-1">{r.message}</p>}
                  <p className="text-xs text-slate-500">
                    Due: {r.due_date}
                    {r.linked_entity_type && (
                      <span className="ml-2">
                        Linked: {r.linked_entity_type} #{r.linked_entity_id}
                      </span>
                    )}
                  </p>
                </div>
              </div>
              <div className="flex gap-2 shrink-0">
                <button onClick={() => openEdit(r)} className="text-xs text-blue-400 hover:text-blue-300">
                  Edit
                </button>
                <button onClick={() => handleDelete(r.id)} className="text-xs text-red-400 hover:text-red-300">
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create / Edit modal */}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editId != null ? "Edit Reminder" : "New Reminder"}>
        <form onSubmit={handleSave} className="space-y-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Title</label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              required
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Due Date</label>
            <input
              type="date"
              value={form.due_date}
              onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
              required
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Message (optional)</label>
            <textarea
              value={form.message}
              onChange={(e) => setForm((f) => ({ ...f, message: e.target.value }))}
              rows={3}
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500 resize-none"
            />
          </div>
          <button
            type="submit"
            disabled={saving}
            className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-sm transition-colors flex items-center justify-center gap-2"
          >
            {saving && <Spinner />}
            {editId != null ? "Update" : "Create"}
          </button>
        </form>
      </Modal>
    </div>
  );
}
