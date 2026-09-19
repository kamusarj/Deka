import { getApiErrorMessage as errorMessage } from "../utils/apiError";
import AdminMFA from "../components/AdminMFA";
import { useEffect, useMemo, useState } from "react";
import { getRoleBadgeClass, getStoredRoleLabel } from "../auth/rolePolicy";
import { useAuth } from "../contexts/useAuth";
import { useToast } from "../contexts/useToast";
import { getToken, setToken } from "../contexts/authStorage";
import "../styles/account.css";
import AccountSubscription from "../components/AccountSubscription";
import {
  authChangePassword,
  authUpdateProfile,
  getMySchool,
  type SchoolInfo,
} from "../services/api";

function formatJoinDate(value: string | null | undefined) {
  if (!value) return "Chưa có dữ liệu";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Chưa có dữ liệu";
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

export default function Account() {
  const { user, refreshUser } = useAuth();
  const { notify } = useToast();
  const [name, setName] = useState(user?.name || "");
  const [school, setSchool] = useState<SchoolInfo | null>(null);
  const [schoolLoading, setSchoolLoading] = useState(true);
  const [schoolError, setSchoolError] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordSaved, setPasswordSaved] = useState(false);
  const [passwordError, setPasswordError] = useState("");

  useEffect(() => {
    setName(user?.name || "");
  }, [user?.name]);

  useEffect(() => {
    let active = true;
    setSchoolLoading(true);
    setSchoolError("");
    getMySchool()
      .then((value) => {
        if (active) setSchool(value);
      })
      .catch((error) => {
        if (active) {
          setSchool(null);
          setSchoolError(errorMessage(error, "Không tải được thông tin trường"));
        }
      })
      .finally(() => {
        if (active) setSchoolLoading(false);
      });
    return () => { active = false; };
  }, [user?.school_id]);

  const initial = useMemo(() => {
    const source = user?.name?.trim() || user?.email || "S";
    return source.slice(0, 1).toUpperCase();
  }, [user?.email, user?.name]);

  async function saveProfile(event: React.FormEvent) {
    event.preventDefault();
    const normalizedName = name.trim();
    if (!normalizedName) return;
    const token = getToken();
    setProfileSaving(true);
    setProfileError("");
    try {
      await authUpdateProfile(normalizedName);
      if (getToken() !== token) return;
      await refreshUser();
      if (getToken() === token) notify("Đã cập nhật thông tin cá nhân", "success");
    } catch (error) {
      setProfileError(errorMessage(error, "Không lưu được thông tin tài khoản"));
    } finally {
      setProfileSaving(false);
    }
  }

  async function savePassword(event: React.FormEvent) {
    event.preventDefault();
    setPasswordError("");
    setPasswordSaved(false);
    if (newPassword === currentPassword) {
      setPasswordError("Mật khẩu mới phải khác mật khẩu hiện tại");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("Mật khẩu xác nhận không khớp");
      return;
    }
    if (newPassword.length < 6) {
      setPasswordError("Mật khẩu mới cần tối thiểu 6 ký tự");
      return;
    }
    const token = getToken();
    if (!token) return;
    setPasswordSaving(true);
    try {
      const response = await authChangePassword(currentPassword, newPassword);
      if (getToken() !== token) return;
      setToken(response.access_token);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordSaved(true);
      await refreshUser();
    } catch (error) {
      setPasswordError(errorMessage(error, "Không đổi được mật khẩu"));
    } finally {
      setPasswordSaving(false);
    }
  }

  return (
    <section className="settings-page account-page">
      <div className="account-page-title"><h1>Tài khoản</h1><p>Thông tin của bạn và những thiết lập cho việc soạn đề.</p></div>
      {user?.must_change_password && <div className="validation-banner error" role="alert">Bạn đang dùng mật khẩu tạm. Hãy đổi mật khẩu để tiếp tục sử dụng workspace.</div>}
      <header className="account-identity">
        <div className="account-avatar" aria-hidden="true">{user?.avatar_url ? <img src={user.avatar_url} alt="" /> : initial}</div>
        <div className="account-identity-copy"><h2>{user?.name || "Giáo viên"}</h2><p>{user?.email || "Chưa có email"}</p></div>
        <div className="account-membership"><span className={`role-group-pill ${getRoleBadgeClass(user?.role)}`}>{getStoredRoleLabel(user?.role)}</span><span>Tham gia {formatJoinDate(user?.created_at)}</span>{!user?.is_active && <span>Đã khóa</span>}</div>
      </header>
      <div className="account-workspace">
        <div className="account-main">
          <div className="account-sheet">
            <section className="account-sheet-section" aria-labelledby="profile-heading">
              <header className="account-section-heading"><h2 id="profile-heading">Thông tin cá nhân</h2><p>Tên hiển thị trên hồ sơ và trong không gian làm việc.</p></header>
          <form className="account-form" onSubmit={saveProfile}>
            <label>
              Họ và tên
              <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Nguyễn Văn A" required maxLength={255} autoComplete="name" />
            </label>
            {profileError && <div className="auth-error account-form-message" role="alert">{profileError}</div>}
            <div className="account-form-actions">
              <button type="submit" disabled={profileSaving || !name.trim() || name.trim() === user?.name}>{profileSaving ? "Đang lưu…" : "Lưu thông tin"}</button>
            </div>
          </form>
            </section>
            <section className="account-sheet-section" aria-labelledby="school-heading">
              <header className="account-section-heading"><h2 id="school-heading">Trường đang giảng dạy</h2><p>Quản trị viên quản lý thông tin và phân trường cho tài khoản.</p></header>
          {schoolLoading ? (
            <div className="account-school-empty">Đang tải thông tin trường…</div>
          ) : schoolError ? (
            <div className="auth-error account-form-message" role="alert">
              {schoolError}
            </div>
          ) : school ? (
            <dl className="account-school-details">
              <div><dt>Tên trường</dt><dd>{school.name}</dd></div>
              <div><dt>Địa chỉ</dt><dd>{school.address || "Chưa cập nhật"}</dd></div>
              <div><dt>Điện thoại</dt><dd>{school.phone || "Chưa cập nhật"}</dd></div>
            </dl>
          ) : (
            <div className="account-school-empty">
              <strong>Chưa được phân trường</strong>
              <p>Liên hệ quản trị viên để được thêm vào đúng trường đang giảng dạy.</p>
            </div>
          )}

            </section>
          </div>
          {user?.role === "super_admin" && <AdminMFA key={user.id} />}
          <details className="account-security" open={user?.must_change_password || undefined}>
            <summary><span><span className="account-disclosure-title">Bảo mật tài khoản</span><span className="account-disclosure-description">{user?.can_change_password ? "Đổi mật khẩu đăng nhập" : "Thông tin đăng nhập qua nhà cung cấp"}</span></span><span className="account-disclosure-arrow" aria-hidden="true">⌄</span></summary>
            <div className="account-security-body">
          {user?.can_change_password ? (
            <form className="account-form account-password-form" onSubmit={savePassword}>
              <label>
                Mật khẩu hiện tại
                <input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required autoComplete="current-password" />
              </label>
              <label>
                Mật khẩu mới
                <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required minLength={6} maxLength={128} autoComplete="new-password" />
              </label>
              <label>
                Xác nhận mật khẩu mới
                <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required minLength={6} maxLength={128} autoComplete="new-password" />
              </label>
              {passwordError && <div className="auth-error account-form-message" role="alert">{passwordError}</div>}
              <div className="account-form-actions">
                <button type="submit" disabled={passwordSaving || !currentPassword || !newPassword || !confirmPassword}>{passwordSaving ? "Đang đổi…" : "Đổi mật khẩu"}</button>
                {passwordSaved && <span className="account-success" role="status">✓ Đổi mật khẩu thành công</span>}
              </div>
            </form>
          ) : (
            <div className="account-oauth-note">

              <div>
                <strong>Tài khoản đăng nhập qua nhà cung cấp</strong>
                <p>Mật khẩu được quản lý bởi Google hoặc Facebook. Hãy đổi mật khẩu tại nhà cung cấp bạn dùng để đăng nhập.</p>
              </div>
            </div>
          )}
            </div>
          </details>
        </div>
        {user && !user.must_change_password && <aside className="account-aside" aria-label="Gói sử dụng và credit"><AccountSubscription key={user.id} /></aside>}
      </div>
    </section>
  );
}
