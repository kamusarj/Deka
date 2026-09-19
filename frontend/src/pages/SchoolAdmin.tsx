import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { SelectControl } from "../components";
import { getRoleBadgeClass, getStoredRoleLabel, isSuperAdminRole } from "../auth/rolePolicy";
import { useAuth } from "../contexts/useAuth";
import {
  assignExistingTeacher,
  createManagedUser,
  createSchool,
  createTeacher,
  deleteManagedUser,
  deleteSchool,
  deleteTeacher,
  getMySchool,
  listAdminUsers,
  listSchools,
  listTeachers,
  listAuditLogs,
  resetManagedPassword,
  transferTeacher,
  updateManagedUser,
  updateSchool,
  updateTeacher,
} from "../services/api";
import type { AuditLogItem, AuthUser, SchoolInfo } from "../services/api";

function apiError(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback;
  const detail = error.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

function SchoolEditor({ school, onSaved, onDeleted }: { school: SchoolInfo; onSaved: (school: SchoolInfo) => void; onDeleted: (id: number) => void }) {
  const [name, setName] = useState(school.name);
  const [address, setAddress] = useState(school.address || "");
  const [phone, setPhone] = useState(school.phone || "");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  async function save() {
    setSaving(true);
    setNotice("");
    try {
      const updated = await updateSchool(school.id, { name, address: address || null, phone: phone || null });
      onSaved(updated);
      setNotice("Đã lưu");
    } catch (error) {
      setNotice(apiError(error, "Không lưu được trường"));
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!confirm(`Xóa trường ${school.name}? Chỉ trường không còn tài khoản hoặc dữ liệu mới được xóa.`)) return;
    setNotice("");
    try {
      await deleteSchool(school.id);
      onDeleted(school.id);
    } catch (error) {
      setNotice(apiError(error, "Không thể xóa trường còn dữ liệu tham chiếu"));
    }
  }

  return (
    <article className="list-item platform-editor-card">
      <div className="list-item-head">
        <strong>{school.name}</strong>
        <span className="badge badge-primary">Trường #{school.id}</span>
      </div>
      <div className="grid two platform-editor-grid">
        <label>Tên trường<input value={name} onChange={(event) => setName(event.target.value)} /></label>
        <label>Địa chỉ<input value={address} onChange={(event) => setAddress(event.target.value)} /></label>
        <label>Điện thoại<input value={phone} onChange={(event) => setPhone(event.target.value)} /></label>
      </div>
      <div className="list-item-footer">
        <small className={notice === "Đã lưu" ? "pass" : "muted"}>{notice || "Chỉnh sửa không làm mất thành viên"}</small>
        <button type="button" className="secondary compact" disabled={saving || name.trim().length < 2} onClick={save}>
          {saving ? "Đang lưu…" : "Lưu trường"}
        </button>
        <button type="button" className="btn-danger compact" onClick={remove}>Xóa trường</button>
      </div>
    </article>
  );
}

function AccountEditor({
  account,
  schools,
  currentUserId,
  onSaved,
  onDeleted,
}: {
  account: AuthUser;
  schools: SchoolInfo[];
  currentUserId: number | undefined;
  onSaved: (account: AuthUser) => void;
  onDeleted: (id: number) => void;
}) {
  const protectedAccount = isSuperAdminRole(account.role) || account.id === currentUserId;
  const [name, setName] = useState(account.name || "");
  const [role, setRole] = useState(account.role);
  const [schoolId, setSchoolId] = useState(account.school_id ? String(account.school_id) : "");
  const [active, setActive] = useState(account.is_active);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  async function save() {
    if (protectedAccount || role === "super_admin") return;
    setSaving(true);
    setNotice("");
    try {
      let updated = await updateManagedUser(account.id, {
        name,
        role: role as "school_admin" | "teacher" | "viewer",
        ...(account.role === "teacher" && role === "teacher" ? {} : { school_id: schoolId ? Number(schoolId) : null }),
        is_active: active,
      });
      if (account.role === "teacher" && updated.role === "teacher" && updated.school_id !== (schoolId ? Number(schoolId) : null)) {
        updated = await transferTeacher(account.id, schoolId ? Number(schoolId) : null);
      }
      onSaved(updated);
      setNotice("Đã lưu");
    } catch (error) {
      setNotice(apiError(error, "Không cập nhật được tài khoản"));
    } finally {
      setSaving(false);
    }
  }

  async function resetPassword() {
    const temporaryPassword = prompt(`Mật khẩu tạm cho ${account.email} (tối thiểu 6 ký tự):`);
    if (!temporaryPassword) return;
    try {
      const result = await resetManagedPassword(account.id, temporaryPassword);
      setNotice(result.message);
    } catch (error) {
      setNotice(apiError(error, "Không đặt lại được mật khẩu"));
    }
  }

  async function remove() {
    if (!confirm(`Vô hiệu hóa và xóa mềm tài khoản ${account.email}?`)) return;
    try {
      await deleteManagedUser(account.id);
      onDeleted(account.id);
    } catch (error) {
      setNotice(apiError(error, "Không xóa được tài khoản"));
    }
  }

  return (
    <article className="list-item platform-editor-card">
      <div className="list-item-head">
        <div>
          <strong>{account.email}</strong>
          <div className="list-item-meta"><span>Tài khoản #{account.id}</span></div>
        </div>
        <span className={`role-group-pill ${getRoleBadgeClass(account.role)}`}>{getStoredRoleLabel(account.role)}</span>
      </div>
      {protectedAccount ? (
        <p className="muted">Tài khoản Super Admin được bảo vệ và không thể sửa tại đây.</p>
      ) : (
        <div className="grid two platform-editor-grid">
          <label>Họ tên<input value={name} onChange={(event) => setName(event.target.value)} /></label>
          <label>
            Quyền
            <SelectControl
              ariaLabel={`Quyền của ${account.email}`}
              value={role}
              onChange={setRole}
              options={[
                { value: "school_admin", label: "School Admin" },
                { value: "teacher", label: "Teacher" },
                { value: "viewer", label: "Viewer" },
              ]}
            />
          </label>
          <label>
            Trường
            <SelectControl
              ariaLabel={`Trường của ${account.email}`}
              value={schoolId}
              onChange={setSchoolId}
              options={[
                { value: "", label: "Chưa thuộc trường" },
                ...schools.map((school) => ({ value: String(school.id), label: school.name })),
              ]}
            />
          </label>
          <label className="platform-active-toggle">
            <input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />
            Tài khoản đang hoạt động
          </label>
        </div>
      )}
      {!protectedAccount && (
        <div className="list-item-footer">
          <small className={notice === "Đã lưu" ? "pass" : notice ? "error" : "muted"}>
            {notice || (role === "school_admin" && !schoolId ? "School Admin bắt buộc phải thuộc trường" : "Quyền được lưu tại server")}
          </small>
          <button type="button" className="secondary compact" disabled={saving || (role === "school_admin" && !schoolId)} onClick={save}>
            {saving ? "Đang lưu…" : "Lưu tài khoản"}
          </button>
          <button type="button" className="ghost-btn compact" onClick={resetPassword}>Đặt mật khẩu tạm</button>
          <button type="button" className="btn-danger compact" onClick={remove}>Xóa tài khoản</button>
        </div>
      )}
    </article>
  );
}

function AuditLogPanel({ items }: { items: AuditLogItem[] }) {
  return (
    <section className="settings-section">
      <div className="dash-section-head"><div><h2>Nhật ký quản trị</h2><p className="muted">Các thay đổi quan trọng trong phạm vi bạn quản lý.</p></div></div>
      {items.length === 0 ? <p className="muted">Chưa có sự kiện quản trị.</p> : (
        <div className="list platform-admin-list">
          {items.slice(0, 20).map((item) => (
            <article className="list-item" key={item.id}>
              <div className="list-item-head"><strong>{item.action}</strong><span className="badge">#{item.id}</span></div>
              <div className="list-item-meta">
                <span>Actor #{item.actor_user_id ?? "hệ thống"}</span>
                <span>{item.target_type} #{item.target_id ?? "—"}</span>
                <span>{new Date(item.created_at).toLocaleString("vi-VN")}</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export default function SchoolAdmin() {
  const { user } = useAuth();
  const isSuperAdmin = isSuperAdminRole(user?.role);
  const [school, setSchool] = useState<SchoolInfo | null>(null);
  const [schools, setSchools] = useState<SchoolInfo[]>([]);
  const [teachers, setTeachers] = useState<AuthUser[]>([]);
  const [accounts, setAccounts] = useState<AuthUser[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [schoolName, setSchoolName] = useState("");
  const [schoolAddress, setSchoolAddress] = useState("");
  const [creatingSchool, setCreatingSchool] = useState(false);
  const [accountEmail, setAccountEmail] = useState("");
  const [accountName, setAccountName] = useState("");
  const [accountPassword, setAccountPassword] = useState("");
  const [accountRole, setAccountRole] = useState("teacher");
  const [accountSchoolId, setAccountSchoolId] = useState("");
  const [creatingAccount, setCreatingAccount] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showAttachForm, setShowAttachForm] = useState(false);
  const [teacherEmail, setTeacherEmail] = useState("");
  const [teacherName, setTeacherName] = useState("");
  const [teacherPassword, setTeacherPassword] = useState("");
  const [existingEmail, setExistingEmail] = useState("");
  const [submittingTeacher, setSubmittingTeacher] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      if (isSuperAdmin) {
        const [schoolRows, accountRows, auditRows] = await Promise.all([listSchools(), listAdminUsers(), listAuditLogs()]);
        setSchools(schoolRows);
        setAccounts(accountRows);
        setAuditLogs(auditRows.items);
      } else {
        const schoolRow = await getMySchool();
        setSchool(schoolRow);
        setTeachers(schoolRow ? await listTeachers() : []);
        setAuditLogs((await listAuditLogs()).items);
      }
    } catch (requestError) {
      setError(apiError(requestError, "Không tải được dữ liệu quản trị"));
    } finally {
      setLoading(false);
    }
  }, [isSuperAdmin]);

  useEffect(() => { loadData(); }, [loadData]);

  async function handleCreateSchool(event: React.FormEvent) {
    event.preventDefault();
    setCreatingSchool(true);
    setError("");
    try {
      const created = await createSchool(schoolName, schoolAddress || undefined);
      setSchools((current) => [...current, created].sort((a, b) => a.name.localeCompare(b.name, "vi")));
      setSchoolName("");
      setSchoolAddress("");
    } catch (requestError) {
      setError(apiError(requestError, "Không tạo được trường"));
    } finally {
      setCreatingSchool(false);
    }
  }

  async function handleCreateTeacher(event: React.FormEvent) {
    event.preventDefault();
    setSubmittingTeacher(true);
    setError("");
    try {
      const created = await createTeacher(teacherEmail, teacherPassword, teacherName);
      setTeachers((current) => [created, ...current]);
      setTeacherEmail(""); setTeacherName(""); setTeacherPassword(""); setShowAddForm(false);
    } catch (requestError) {
      setError(apiError(requestError, "Không tạo được Teacher"));
    } finally {
      setSubmittingTeacher(false);
    }
  }

  async function handleCreateAccount(event: React.FormEvent) {
    event.preventDefault();
    setCreatingAccount(true);
    setError("");
    try {
      const created = await createManagedUser({
        email: accountEmail,
        password: accountPassword,
        name: accountName,
        role: accountRole as "school_admin" | "teacher" | "viewer",
        school_id: accountSchoolId ? Number(accountSchoolId) : null,
      });
      setAccounts((current) => [created, ...current]);
      setAccountEmail(""); setAccountName(""); setAccountPassword("");
      setAccountRole("teacher"); setAccountSchoolId("");
    } catch (requestError) {
      setError(apiError(requestError, "Không tạo được tài khoản"));
    } finally {
      setCreatingAccount(false);
    }
  }

  async function handleAttachTeacher(event: React.FormEvent) {
    event.preventDefault();
    setSubmittingTeacher(true);
    setError("");
    try {
      const attached = await assignExistingTeacher(existingEmail);
      setTeachers((current) => [attached, ...current]);
      setExistingEmail(""); setShowAttachForm(false);
    } catch (requestError) {
      setError(apiError(requestError, "Không thêm được Teacher"));
    } finally {
      setSubmittingTeacher(false);
    }
  }

  async function toggleTeacher(teacher: AuthUser) {
    try {
      const updated = await updateTeacher(teacher.id, { is_active: !teacher.is_active });
      setTeachers((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (requestError) {
      setError(apiError(requestError, "Không cập nhật được Teacher"));
    }
  }

  async function removeTeacher(teacher: AuthUser) {
    if (!confirm(`Gỡ ${teacher.email} khỏi trường? Tài khoản và dữ liệu vẫn được giữ lại.`)) return;
    try {
      await deleteTeacher(teacher.id);
      setTeachers((current) => current.filter((item) => item.id !== teacher.id));
    } catch (requestError) {
      setError(apiError(requestError, "Không gỡ được Teacher"));
    }
  }

  if (loading) return <div className="settings-page"><p className="muted">Đang tải…</p></div>;

  if (isSuperAdmin) {
    return (
      <section className="settings-page platform-admin-page">
        <div className="page-intro"><h1>Quản trị toàn hệ thống</h1><p>Quản lý tất cả trường học và tài khoản từ một nơi.</p></div>
        {error && <div className="auth-error">{error}</div>}
        <dl className="settings-summary">
          <div><dt>Trường học</dt><dd>{schools.length}</dd></div>
          <div><dt>Tài khoản</dt><dd>{accounts.length}</dd></div>
          <div><dt>Đang hoạt động</dt><dd>{accounts.filter((account) => account.is_active).length}</dd></div>
        </dl>

        <section className="settings-section">
          <div className="dash-section-head"><div><h2>Tất cả trường học</h2><p className="muted">Tạo mới và chỉnh sửa thông tin trường.</p></div></div>
          <form className="panel platform-create-school" onSubmit={handleCreateSchool}>
            <label>Tên trường<input value={schoolName} onChange={(event) => setSchoolName(event.target.value)} required minLength={2} placeholder="THPT Nguyễn Huệ" /></label>
            <label>Địa chỉ<input value={schoolAddress} onChange={(event) => setSchoolAddress(event.target.value)} placeholder="Địa chỉ trường" /></label>
            <button type="submit" disabled={creatingSchool}>{creatingSchool ? "Đang tạo…" : "+ Tạo trường"}</button>
          </form>
          <div className="list platform-admin-list">
            {schools.map((item) => <SchoolEditor key={item.id} school={item} onSaved={(updated) => setSchools((current) => current.map((row) => row.id === updated.id ? updated : row))} onDeleted={(id) => setSchools((current) => current.filter((row) => row.id !== id))} />)}
          </div>
        </section>

        <section className="settings-section">
          <div className="dash-section-head"><div><h2>Tất cả tài khoản</h2><p className="muted">Đổi quyền, trường và trạng thái của mọi tài khoản không phải Super Admin.</p></div></div>
          <form className="panel platform-create-account" onSubmit={handleCreateAccount}>
            <label>Email<input type="email" value={accountEmail} onChange={(event) => setAccountEmail(event.target.value)} required /></label>
            <label>Họ tên<input value={accountName} onChange={(event) => setAccountName(event.target.value)} /></label>
            <label>Mật khẩu<input type="password" minLength={6} value={accountPassword} onChange={(event) => setAccountPassword(event.target.value)} required /></label>
            <label>
              Quyền
              <SelectControl
                ariaLabel="Quyền tài khoản mới"
                value={accountRole}
                onChange={setAccountRole}
                options={[
                  { value: "school_admin", label: "School Admin" },
                  { value: "teacher", label: "Teacher" },
                  { value: "viewer", label: "Viewer" },
                ]}
              />
            </label>
            <label>
              Trường
              <SelectControl
                ariaLabel="Trường của tài khoản mới"
                value={accountSchoolId}
                onChange={setAccountSchoolId}
                options={[
                  { value: "", label: "Chưa thuộc trường" },
                  ...schools.map((item) => ({ value: String(item.id), label: item.name })),
                ]}
              />
            </label>
            <button type="submit" disabled={creatingAccount || (accountRole === "school_admin" && !accountSchoolId)}>
              {creatingAccount ? "Đang tạo…" : "+ Tạo tài khoản"}
            </button>
          </form>
          <div className="list platform-admin-list">
            {accounts.map((account) => (
              <AccountEditor key={account.id} account={account} schools={schools} currentUserId={user?.id} onSaved={(updated) => setAccounts((current) => current.map((row) => row.id === updated.id ? updated : row))} onDeleted={(id) => setAccounts((current) => current.filter((row) => row.id !== id))} />
            ))}
          </div>
        </section>
        <AuditLogPanel items={auditLogs} />
      </section>
    );
  }

  return (
    <section className="settings-page">
      <div className="page-intro"><h1>Quản lý Teacher</h1><p>School Admin chỉ quản lý Teacher thuộc trường của mình.</p></div>
      {error && <div className="auth-error">{error}</div>}
      {!school ? (
        <div className="panel"><strong>Chưa được gán trường</strong><p className="muted">Liên hệ Super Admin để gán tài khoản vào một trường.</p></div>
      ) : (
        <>
          <dl className="settings-summary">
            <div><dt>Trường</dt><dd>{school.name}</dd></div>
            <div><dt>Địa chỉ</dt><dd>{school.address || "—"}</dd></div>
            <div><dt>Teacher</dt><dd>{teachers.length}</dd></div>
          </dl>
          <section className="settings-section">
            <div className="dash-section-head">
              <h2>Teacher trong trường</h2>
              <div className="row-wrap">
                <button type="button" className="secondary compact" onClick={() => { setShowAddForm((value) => !value); setShowAttachForm(false); }}>{showAddForm ? "Hủy" : "+ Tạo Teacher"}</button>
                <button type="button" className="secondary compact" onClick={() => { setShowAttachForm((value) => !value); setShowAddForm(false); }}>{showAttachForm ? "Hủy" : "+ Thêm tài khoản có sẵn"}</button>
              </div>
            </div>
            {showAddForm && (
              <form className="panel settings-form" onSubmit={handleCreateTeacher}>
                <label>Email<input type="email" value={teacherEmail} onChange={(event) => setTeacherEmail(event.target.value)} required /></label>
                <label>Họ tên<input value={teacherName} onChange={(event) => setTeacherName(event.target.value)} /></label>
                <label>Mật khẩu<input type="password" minLength={6} value={teacherPassword} onChange={(event) => setTeacherPassword(event.target.value)} required /></label>
                <button type="submit" disabled={submittingTeacher}>{submittingTeacher ? "Đang tạo…" : "Tạo Teacher"}</button>
              </form>
            )}
            {showAttachForm && (
              <form className="panel settings-form" onSubmit={handleAttachTeacher}>
                <label>Email Teacher chưa thuộc trường<input type="email" value={existingEmail} onChange={(event) => setExistingEmail(event.target.value)} required /></label>
                <button type="submit" disabled={submittingTeacher}>{submittingTeacher ? "Đang thêm…" : "Thêm vào trường"}</button>
              </form>
            )}
            {teachers.length === 0 ? <p className="muted">Trường chưa có Teacher.</p> : (
              <div className="list">
                {teachers.map((teacher) => (
                  <article key={teacher.id} className="list-item">
                    <div className="list-item-head"><strong>{teacher.name || teacher.email}</strong><span className={`badge ${teacher.is_active ? "badge-success" : "badge-danger"}`}>{teacher.is_active ? "Hoạt động" : "Đã khóa"}</span></div>
                    <div className="list-item-meta"><span>{teacher.email}</span><span>Teacher</span></div>
                    <div className="list-item-footer">
                      <small className="muted">Chỉ thuộc trường {school.name}</small>
                      <div className="row-wrap">
                        <button type="button" className="secondary compact" onClick={() => toggleTeacher(teacher)}>{teacher.is_active ? "Khóa" : "Mở khóa"}</button>
                        <button type="button" className="ghost-btn compact" onClick={() => removeTeacher(teacher)}>Gỡ khỏi trường</button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
          <AuditLogPanel items={auditLogs} />
        </>
      )}
    </section>
  );
}
