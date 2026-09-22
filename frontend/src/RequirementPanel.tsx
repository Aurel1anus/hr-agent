import { CheckCircle2, Pencil, Save, Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, apiUrl } from "./api";

type Item = { name: string; description: string; evidence_required?: boolean };
type Profile = Record<string, any>;

const lines = (values: string[] = []) => values.join("\n");
const toLines = (value?: string) => (value || "").split("\n").map((item) => item.trim()).filter(Boolean);
const itemLines = (values: Item[] = []) => values.map((item) => `${item.name}：${item.description}`).join("\n");
const toItems = (value: string): Item[] => toLines(value).map((line) => {
  const splitAt = line.search(/[：:]/);
  return splitAt < 0
    ? { name: line, description: line, evidence_required: true }
    : { name: line.slice(0, splitAt).trim(), description: line.slice(splitAt + 1).trim(), evidence_required: true };
}).filter((item) => item.name && item.description);

export default function RequirementPanel({ jobId, notify }: { jobId: number; notify: (x: string) => void }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [streamStatus, setStreamStatus] = useState("");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState<Profile>({});
  const load = () => api<Profile>(`/jobs/${jobId}/requirement-profile`).then(setProfile).catch(() => undefined);
  useEffect(() => { void load(); }, [jobId]);
  const generate = async () => {
    setBusy(true); setStreamStatus("正在创建生成任务…");
    try {
      const response = await fetch(apiUrl(`/jobs/${jobId}/requirement-profile/generate/stream`), { method: "POST", headers: { "Content-Type": "application/json", Accept: "text/event-stream" }, body: JSON.stringify({ extra_notes: notes || null }) });
      if (!response.ok || !response.body) { const body = await response.json().catch(() => null); throw new Error(body?.detail || body?.message || "生成失败，请重试。"); }
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ""; let completed = false;
      const handleEvent = (block: string) => {
        const name = block.match(/^event:\s*(.+)$/m)?.[1]; const dataLine = block.match(/^data:\s*(.+)$/m)?.[1];
        if (!name || !dataLine) return;
        const data = JSON.parse(dataLine);
        if (name === "status" || name === "progress" || name === "run") setStreamStatus(data.message || "正在生成招聘画像…");
        if (name === "result") { setProfile(data.profile); setEditing(false); completed = true; setStreamStatus("招聘画像已生成"); notify(data.profile?._ai?.status === "degraded" ? "招聘画像已生成，但 AI 输出已自动修复" : "招聘画像已生成，请人工核对后确认"); }
        if (name === "error") throw new Error(data.message || "AI 分析暂时失败，请重试。");
      };
      while (true) { const { done, value } = await reader.read(); buffer += decoder.decode(value || new Uint8Array(), { stream: !done }); let divider; while ((divider = buffer.indexOf("\n\n")) >= 0) { handleEvent(buffer.slice(0, divider)); buffer = buffer.slice(divider + 2); } if (done) break; }
      if (!completed) throw new Error("生成连接已结束，请重试。");
    } catch (e) { notify(e instanceof Error ? e.message : "生成失败"); } finally { setBusy(false); setStreamStatus(""); }
  };
  const beginEdit = () => { if (!profile) return; setDraft({ ...profile, must_have_text: itemLines(profile.must_have), preferred_text: itemLines(profile.preferred), skills_text: lines(profile.skills), soft_skills_text: lines(profile.soft_skills), negative_signals_text: lines(profile.negative_signals), verification_questions_text: lines(profile.verification_questions) }); setEditing(true); };
  const save = async () => { if (!profile) return; setSaving(true); try { const updated = await api<Profile>(`/requirement-profiles/${profile.id}`, { method: "PUT", body: JSON.stringify({ must_have: toItems(draft.must_have_text), preferred: toItems(draft.preferred_text), skills: toLines(draft.skills_text), soft_skills: toLines(draft.soft_skills_text), negative_signals: toLines(draft.negative_signals_text), verification_questions: toLines(draft.verification_questions_text), ai_summary: draft.ai_summary }) }); setProfile(updated); setEditing(false); notify("人工修改已保存，请确认画像"); } catch (e) { notify(e instanceof Error ? e.message : "保存失败"); } finally { setSaving(false); } };
  const confirm = async () => { if (!profile) return; try { setProfile(await api<Profile>(`/requirement-profiles/${profile.id}/confirm`, { method: "POST" })); notify("招聘画像已确认，可用于 AI 简历评估"); } catch (e) { notify(e instanceof Error ? e.message : "确认失败"); } };
  const editText = (key: string, label: string, value: string, hint?: string) => <label className="profile-editor-field"><span>{label}</span>{hint && <small>{hint}</small>}<textarea value={value} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} /></label>;
  const confirmed = profile?.status === "confirmed";
  return <section className="panel requirement-panel">
    <div className="requirement-heading"><div><div className="requirement-kicker"><Sparkles size={15} /> AI 辅助</div><h3>招聘画像</h3><p>{profile ? (confirmed ? "已确认，可作为简历评估依据" : "请核对并补充后确认，避免 AI 直接替你作决定") : "先补充业务偏好，再由 AI 生成初稿"}</p></div><span className={`profile-status ${confirmed ? "confirmed" : "draft"}`}>{confirmed ? "已确认" : profile ? "待确认" : "未生成"}</span></div>
    <div className="requirement-actions"><button className="generate-action" onClick={generate} disabled={busy || editing}><Sparkles size={16} />{busy ? "AI 正在生成…" : profile ? "AI 重新生成" : "AI 生成招聘画像"}</button>{profile && !editing && <><button className="edit-action" onClick={beginEdit}><Pencil size={16} />人工修改</button><button className="confirm-action" onClick={confirm} disabled={confirmed}><CheckCircle2 size={16} />{confirmed ? "画像已确认" : "确认画像"}</button></>}</div>
    {busy && <div className="ai-stream-status"><span></span>{streamStatus || "正在分析岗位信息…"}</div>}
    {!profile && <label className="profile-notes"><span>业务补充（可选）</span><textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="例如：更看重平台运营经验，学校不是重点" /></label>}
    {profile && !editing && <div className="profile-preview"><div className="profile-summary"><b>岗位摘要</b><p>{profile.ai_summary}</p></div><div className="requirement-grid"><div><b>硬性要求</b>{profile.must_have?.map((item: Item) => <span key={item.name}>{item.name}<small>{item.description}</small></span>)}</div><div><b>加分项</b>{profile.preferred?.map((item: Item) => <span key={item.name}>{item.name}<small>{item.description}</small></span>)}</div></div><div className="profile-tags"><b>技能标签</b><div>{profile.skills?.map((skill: string) => <span key={skill}>{skill}</span>)}</div></div></div>}
    {profile && editing && <div className="profile-editor"><div className="editor-notice"><Pencil size={16} />正在编辑 Revision {profile.revision}。保存后会创建新草稿，需再次确认。</div>{editText("ai_summary", "岗位摘要", draft.ai_summary || "")}{editText("must_have_text", "硬性要求", draft.must_have_text ?? itemLines(profile.must_have), "每行一项，格式：名称：说明")}{editText("preferred_text", "加分项", draft.preferred_text ?? itemLines(profile.preferred), "每行一项，格式：名称：说明")}{editText("skills_text", "技能标签", draft.skills_text ?? lines(profile.skills), "每行一个标签")}{editText("soft_skills_text", "软技能", draft.soft_skills_text ?? lines(profile.soft_skills), "每行一项")}{editText("negative_signals_text", "负面信号", draft.negative_signals_text ?? lines(profile.negative_signals), "每行一项，可留空")}{editText("verification_questions_text", "核验问题", draft.verification_questions_text ?? lines(profile.verification_questions), "每行一个面试追问")}<div className="editor-actions"><button className="secondary" onClick={() => setEditing(false)} disabled={saving}><X size={16} />取消</button><button className="confirm-action" onClick={save} disabled={saving}><Save size={16} />{saving ? "正在保存…" : "保存人工修改"}</button></div></div>}
  </section>;
}
