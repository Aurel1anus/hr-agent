import { useState } from "react";
import { api } from "./api";

export type Interview = {
  id: number;
  round_number: number;
  round_name: string;
  status: "scheduling" | "scheduled" | "completed" | "cancelled";
  candidate_availability?: string;
  interviewer_availability?: string;
  scheduled_start_at?: string;
  scheduled_end_at?: string;
  interviewer_name?: string;
  mode?: "online" | "offline";
  location?: string;
  meeting_url?: string;
  feedback?: string;
  result?: string;
  cancel_reason?: string;
};

const format = (v?: string) =>
  v
    ? new Intl.DateTimeFormat("zh-CN", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "Asia/Shanghai",
      }).format(new Date(v))
    : "未安排";
const localInput = (v?: string) =>
  v
    ? new Date(v)
        .toLocaleString("sv-SE", { timeZone: "Asia/Shanghai" })
        .slice(0, 16)
    : "";

function ScheduleForm({
  interview,
  ownerName,
  reschedule,
  done,
  notify,
}: {
  interview: Interview;
  ownerName?: string;
  reschedule: boolean;
  done: () => void;
  notify: (x: string) => void;
}) {
  const [start, setStart] = useState(localInput(interview.scheduled_start_at));
  const [end, setEnd] = useState(localInput(interview.scheduled_end_at));
  const [name, setName] = useState(
    interview.interviewer_name || ownerName || "",
  );
  const [mode, setMode] = useState<"online" | "offline">(
    interview.mode || "online",
  );
  const [location, setLocation] = useState(interview.location || "");
  const [url, setUrl] = useState(interview.meeting_url || "");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      await api(
        `/interviews/${interview.id}/${reschedule ? "reschedule" : "schedule"}`,
        {
          method: "POST",
          body: JSON.stringify({
            scheduled_start_at: new Date(start).toISOString(),
            scheduled_end_at: new Date(end).toISOString(),
            interviewer_name: name,
            mode,
            location: location || null,
            meeting_url: url || null,
          }),
        },
      );
      notify(reschedule ? "面试时间已调整" : "面试时间已确认");
      done();
    } catch (e) {
      notify(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="interview-form">
      <div className="two-fields">
        <label>
          开始时间 <sup>*</sup>
          <input
            type="datetime-local"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label>
          结束时间 <sup>*</sup>
          <input
            type="datetime-local"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
      </div>
      <label>
        面试官 <sup>*</sup>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="默认岗位负责人"
        />
      </label>
      <label>
        形式{" "}
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as "online" | "offline")}
        >
          <option value="online">线上</option>
          <option value="offline">线下</option>
        </select>
      </label>
      {mode === "online" ? (
        <label>
          会议链接 <sup>*</sup>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://..."
          />
        </label>
      ) : (
        <label>
          面试地点 <sup>*</sup>
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="会议室或办公地点"
          />
        </label>
      )}
      <button
        className="primary"
        disabled={
          busy ||
          !start ||
          !end ||
          !name ||
          (mode === "online" && !url) ||
          (mode === "offline" && !location)
        }
        onClick={submit}
      >
        {busy ? "保存中..." : reschedule ? "确认改期" : "确认面试时间"}
      </button>
    </div>
  );
}

export function InterviewPanel({
  applicationId,
  stage,
  ownerName,
  current,
  interviews,
  refresh,
  notify,
}: {
  applicationId: number;
  stage: string;
  ownerName?: string;
  current?: Interview;
  interviews: Interview[];
  refresh: () => void;
  notify: (x: string) => void;
}) {
  const [creating, setCreating] = useState(false),
    [round, setRound] = useState("一面"),
    [candidate, setCandidate] = useState(""),
    [interviewer, setInterviewer] = useState(""),
    [editing, setEditing] = useState(false),
    [feedback, setFeedback] = useState(""),
    [result, setResult] = useState("pass"),
    [nextName, setNextName] = useState("二面"),
    [cancelling, setCancelling] = useState(false),
    [reason, setReason] = useState(""),
    [disposition, setDisposition] = useState("reschedule"),
    [busy, setBusy] = useState(false);
  const create = async () => {
    setBusy(true);
    try {
      await api(`/applications/${applicationId}/interviews`, {
        method: "POST",
        body: JSON.stringify({
          round_name: round,
          candidate_availability: candidate || null,
          interviewer_availability: interviewer || null,
        }),
      });
      notify("已进入约面");
      setCreating(false);
      refresh();
    } catch (e) {
      notify(e instanceof Error ? e.message : "创建失败");
    } finally {
      setBusy(false);
    }
  };
  const availability = async () => {
    if (!current) return;
    setBusy(true);
    try {
      await api(`/interviews/${current.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          candidate_availability: candidate || null,
          interviewer_availability: interviewer || null,
        }),
      });
      notify("可用时间已更新");
      refresh();
    } catch (e) {
      notify(e instanceof Error ? e.message : "更新失败");
    } finally {
      setBusy(false);
    }
  };
  const complete = async () => {
    if (!current) return;
    setBusy(true);
    try {
      await api(`/interviews/${current.id}/complete`, { method: "POST" });
      notify("面试已完成，已创建面评待办");
      refresh();
    } catch (e) {
      notify(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  };
  const submitFeedback = async () => {
    if (!current) return;
    setBusy(true);
    try {
      await api(`/interviews/${current.id}/feedback`, {
        method: "POST",
        body: JSON.stringify({
          feedback: feedback || null,
          result,
          nextName: result === "next_round" ? nextName : undefined,
          next_round_name: result === "next_round" ? nextName : undefined,
        }),
      });
      notify("面评已保存");
      refresh();
    } catch (e) {
      notify(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };
  const cancel = async () => {
    if (!current) return;
    setBusy(true);
    try {
      await api(`/interviews/${current.id}/cancel`, {
        method: "POST",
        body: JSON.stringify({ reason: reason || null, disposition }),
      });
      notify("面试已取消");
      setCancelling(false);
      refresh();
    } catch (e) {
      notify(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <section className="drawer-section interview-panel">
        <h3>面试</h3>
        {stage === "interviewer_review" && !current && !creating && (
          <button className="primary" onClick={() => setCreating(true)}>
            进入约面
          </button>
        )}
        {creating && (
          <div className="interview-form">
            <label>
              轮次名称 <sup>*</sup>
              <input value={round} onChange={(e) => setRound(e.target.value)} />
            </label>
            <label>
              候选人可用时间
              <textarea
                value={candidate}
                onChange={(e) => setCandidate(e.target.value)}
                placeholder="例如：周三下午 2 点后"
              />
            </label>
            <label>
              面试官可用时间
              <textarea
                value={interviewer}
                onChange={(e) => setInterviewer(e.target.value)}
                placeholder="例如：周三 15:00–17:00"
              />
            </label>
            <button
              className="primary"
              disabled={!round.trim() || busy}
              onClick={create}
            >
              创建并进入约面
            </button>
          </div>
        )}
        {current && (
          <>
            <div className="current-interview">
              <b>
                {current.round_name} ·{" "}
                {current.status === "scheduling"
                  ? "约面中"
                  : current.status === "scheduled"
                    ? "待面试"
                    : current.status === "completed"
                      ? "待面评"
                      : "已取消"}
              </b>
              <span>{format(current.scheduled_start_at)}</span>
              {current.interviewer_name && (
                <span>面试官：{current.interviewer_name}</span>
              )}
            </div>
            {current.status === "scheduling" && (
              <div className="interview-form">
                <label>
                  候选人可用时间
                  <textarea
                    value={candidate || current.candidate_availability || ""}
                    onChange={(e) => setCandidate(e.target.value)}
                  />
                </label>
                <label>
                  面试官可用时间
                  <textarea
                    value={
                      interviewer || current.interviewer_availability || ""
                    }
                    onChange={(e) => setInterviewer(e.target.value)}
                  />
                </label>
                <button onClick={availability} disabled={busy}>
                  保存可用时间
                </button>
                {!editing ? (
                  <button className="primary" onClick={() => setEditing(true)}>
                    确认面试时间
                  </button>
                ) : (
                  <ScheduleForm
                    interview={current}
                    ownerName={ownerName}
                    reschedule={false}
                    done={() => {
                      setEditing(false);
                      refresh();
                    }}
                    notify={notify}
                  />
                )}
              </div>
            )}
            {current.status === "scheduled" && (
              <div className="quick-actions">
                <button onClick={() => setEditing(!editing)}>重新约面</button>
                <button onClick={() => setCancelling(!cancelling)}>
                  取消面试
                </button>
                <button className="primary" onClick={complete} disabled={busy}>
                  面试完成
                </button>
                {editing && (
                  <ScheduleForm
                    interview={current}
                    ownerName={ownerName}
                    reschedule
                    done={() => {
                      setEditing(false);
                      refresh();
                    }}
                    notify={notify}
                  />
                )}
              </div>
            )}
            {current.status === "completed" && (
              <div className="interview-form">
                <label>
                  面评
                  <textarea
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    placeholder="可留空"
                  />
                </label>
                <label>
                  结果{" "}
                  <select
                    value={result}
                    onChange={(e) => setResult(e.target.value)}
                  >
                    <option value="pass">通过</option>
                    <option value="next_round">进入下一轮</option>
                    <option value="reject">淘汰</option>
                  </select>
                </label>
                {result === "next_round" && (
                  <label>
                    下一轮名称 <sup>*</sup>
                    <input
                      value={nextName}
                      onChange={(e) => setNextName(e.target.value)}
                    />
                  </label>
                )}
                <button
                  className="primary"
                  onClick={submitFeedback}
                  disabled={
                    busy || (result === "next_round" && !nextName.trim())
                  }
                >
                  提交面评
                </button>
              </div>
            )}
            {cancelling && (
              <div className="interview-form">
                <label>
                  取消原因（可选）
                  <textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                </label>
                <label>
                  后续处理{" "}
                  <select
                    value={disposition}
                    onChange={(e) => setDisposition(e.target.value)}
                  >
                    <option value="reschedule">继续约面</option>
                    <option value="withdraw">候选人退出</option>
                    <option value="reject">招聘方淘汰</option>
                  </select>
                </label>
                <button
                  className="danger-button"
                  onClick={cancel}
                  disabled={busy}
                >
                  确认取消
                </button>
              </div>
            )}
          </>
        )}
      </section>
      <section className="drawer-section">
        <h3>面试记录</h3>
        {interviews.length ? (
          interviews.map((i) => (
            <div className="mini-task" key={i.id}>
              <b>
                {i.round_name} ·{" "}
                {i.status === "cancelled"
                  ? "已取消"
                  : i.result === "next_round"
                    ? "进入下一轮"
                    : i.result === "pass"
                      ? "通过"
                      : i.result === "reject"
                        ? "淘汰"
                        : i.status === "completed"
                          ? "待面评"
                          : i.status === "scheduled"
                            ? "待面试"
                            : "约面中"}
              </b>
              <span>
                {format(i.scheduled_start_at)}{" "}
                {i.interviewer_name ? `· ${i.interviewer_name}` : ""}
              </span>
            </div>
          ))
        ) : (
          <span className="muted">暂无面试记录</span>
        )}
      </section>
    </>
  );
}
