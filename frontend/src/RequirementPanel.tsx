import { useEffect, useState } from "react";
import { api } from "./api";

export default function RequirementPanel({ jobId, notify }: { jobId: number; notify: (x: string) => void }) {
  const [profile, setProfile] = useState<any>(null), [notes, setNotes] = useState(""), [busy, setBusy] = useState(false);
  const load = () => api<any>(`/jobs/${jobId}/requirement-profile`).then(setProfile).catch(() => undefined);
  useEffect(() => { void load(); }, [jobId]);
  const generate = async () => { setBusy(true); try { const p = await api<any>(`/jobs/${jobId}/requirement-profile/generate`, { method: "POST", body: JSON.stringify({ extra_notes: notes || null }) }); setProfile(p); notify("招聘画像已生成"); } catch (e) { notify(e instanceof Error ? e.message : "生成失败"); } finally { setBusy(false); } };
  const confirm = async () => { if (!profile) return; try { setProfile(await api<any>(`/requirement-profiles/${profile.id}/confirm`, { method: "POST" })); notify("招聘画像已确认"); } catch (e) { notify(e instanceof Error ? e.message : "确认失败"); } };
  return <section className="panel requirement-panel"><div className="drawer-section-title"><div><h3>AI 招聘画像</h3><span className="muted">{profile ? `Revision ${profile.revision} · ${profile.status === "confirmed" ? "已确认" : "待确认"}` : "未生成"}</span></div><button className="primary" onClick={generate} disabled={busy}>{busy ? "生成中..." : "AI 生成"}</button></div><textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="补充业务偏好，例如：更看重平台运营经验，学校不是重点" />{profile && <><p>{profile.ai_summary}</p><div className="requirement-grid"><div><b>硬性要求</b>{profile.must_have?.map((x: any) => <span key={x.name}>{x.name}：{x.description}</span>)}</div><div><b>加分项</b>{profile.preferred?.map((x: any) => <span key={x.name}>{x.name}：{x.description}</span>)}</div></div><button onClick={confirm} disabled={profile.status === "confirmed"}>确认画像</button></>}</section>;
}
