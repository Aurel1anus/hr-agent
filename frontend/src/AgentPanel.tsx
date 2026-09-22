import { useState } from "react";
import { api } from "./api";

type Props = { applicationId: number; candidateId: number; notify: (x: string) => void };

export default function AgentPanel({ applicationId, candidateId, notify }: Props) {
  const [loading, setLoading] = useState(false), [data, setData] = useState<any>(null), [memories, setMemories] = useState<any[]>([]);
  const run = async () => { setLoading(true); try { const x = await api<any>(`/applications/${applicationId}/copilot`, { method: "POST" }); setData(x); if (x._ai?.status === "failed") notify("AI 分析暂时失败，请重试。"); else if (x._ai?.status === "degraded") notify("AI 建议已生成，但 AI 输出已自动修复"); const m = await api<any[]>(`/candidates/${candidateId}/memories`); setMemories(m); } catch (e) { notify(e instanceof Error ? e.message : "AI 分析失败"); } finally { setLoading(false); } };
  const approve = async (callId: number, payload: any) => { try { await api(`/agent/tool-calls/${callId}/approve`, { method: "POST", body: JSON.stringify(payload) }); notify("AI 建议已转为待办"); setData({ ...data, next_actions: [] }); } catch (e) { notify(e instanceof Error ? e.message : "执行失败"); } };
  return <section className="drawer-section agent-panel">
    <div className="drawer-section-title"><h3>AI Copilot</h3><button onClick={run} disabled={loading}>{loading ? "分析中..." : "生成建议"}</button></div>
    {!data ? <p className="muted">基于当前候选人、岗位、简历、记忆和招聘记录生成建议。</p> : <>
      <p>{data.summary}</p><div className="info-grid"><span>当前状态<b>{data.current_status}</b></span><span>风险<b>{data.risks?.length ? data.risks.join("；") : "暂无"}</b></span></div>
      {data.memory_highlights?.length > 0 && <><h4>关键记忆</h4>{data.memory_highlights.map((m: any) => <p className="muted" key={m.id}>{m.content}</p>)}</>}
      {data.next_actions?.map((a: any) => <div className="agent-action" key={a.tool_call_id}><p>{a.reason}</p><button className="primary" onClick={() => approve(a.tool_call_id, a.suggested_payload)}>确认创建待办</button></div>)}
    </>}
    <h4>候选人记忆</h4>{memories.map((m) => <p className="muted" key={m.id}>{m.content}</p>)}
  </section>;
}
