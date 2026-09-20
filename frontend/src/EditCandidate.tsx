import { useState } from 'react'
import { X } from 'lucide-react'
import { api } from './api'

type Candidate = { id: number; name: string; phone?: string; email?: string; school?: string; major?: string; graduation_year?: number; current_city?: string; source?: string; resume_url?: string }

export default function EditCandidate({ candidate, close, saved, notify }: { candidate: Candidate; close: () => void; saved: () => Promise<void>; notify: (message: string) => void }) {
  const [form, setForm] = useState({ name: candidate.name, phone: candidate.phone || '', email: candidate.email || '', school: candidate.school || '', major: candidate.major || '', graduation_year: candidate.graduation_year ? String(candidate.graduation_year) : '', current_city: candidate.current_city || '', source: candidate.source || '', resume_url: candidate.resume_url || '' })
  const [saving, setSaving] = useState(false)
  const update = (key: string, value: string) => setForm(previous => ({ ...previous, [key]: value }))
  const submit = async () => {
    setSaving(true)
    try {
      await api(`/candidates/${candidate.id}`, { method: 'PATCH', body: JSON.stringify({ ...form, graduation_year: form.graduation_year ? Number(form.graduation_year) : null }) })
      notify('候选人基础信息已更新')
      await saved()
    } catch (error) { notify(error instanceof Error ? error.message : '保存失败，请重试。') } finally { setSaving(false) }
  }
  return <div className="modal-backdrop"><div className="modal"><div className="modal-head"><h2>编辑基础信息</h2><button className="icon-button" onClick={close}><X size={19}/></button></div><div className="two-fields"><label>姓名<input value={form.name} onChange={e=>update('name',e.target.value)}/></label><label>手机号<input value={form.phone} onChange={e=>update('phone',e.target.value)}/></label></div><div className="two-fields"><label>邮箱<input value={form.email} onChange={e=>update('email',e.target.value)}/></label><label>学校<input value={form.school} onChange={e=>update('school',e.target.value)}/></label></div><div className="two-fields"><label>专业<input value={form.major} onChange={e=>update('major',e.target.value)}/></label><label>毕业年份<input value={form.graduation_year} onChange={e=>update('graduation_year',e.target.value)} inputMode="numeric"/></label></div><div className="two-fields"><label>当前城市<input value={form.current_city} onChange={e=>update('current_city',e.target.value)}/></label><label>来源<input value={form.source} onChange={e=>update('source',e.target.value)}/></label></div><label>简历链接<input value={form.resume_url} onChange={e=>update('resume_url',e.target.value)}/></label><div className="modal-actions"><button className="secondary" onClick={close}>取消</button><button className="primary" disabled={!form.name||saving} onClick={submit}>{saving?'正在保存...':'保存修改'}</button></div></div></div>
}
