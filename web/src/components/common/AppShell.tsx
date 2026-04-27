"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import telertLogo from "../../../assets/图片1.png";
import { useAuth } from "@/components/common/AuthProvider";
import { type Locale } from "@/lib/i18n";
import { useI18n } from "@/components/common/LocaleProvider";

const languageOptions: Array<{ value: Locale; label: string }> = [
  { value: "zh", label: "中文" },
  { value: "en", label: "EN" }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const userMenuRef = useRef<HTMLDivElement | null>(null);
  const { locale, setLocale } = useI18n();
  const { isReady, logout, user } = useAuth();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const text =
    locale === "zh"
      ? {
          title: "TeleRT",
          subtitle: "AI内生安全攻防评治一体化平台",
          runs: "运行列表",
          leaderboard: "排行榜",
          newRun: "新建任务",
          login: "登录",
          logout: "退出",
          signingOut: "退出中...",
          accountMenu: "账号菜单",
          roleAdmin: "管理员",
          roleUser: "用户"
        }
      : {
          title: "Lingyi TeleRT",
          subtitle: "LLM Red Team Evaluation Console",
          runs: "Runs",
          leaderboard: "Leaderboard",
          newRun: "New Run",
          login: "Login",
          logout: "Logout",
          signingOut: "Signing out...",
          accountMenu: "Account menu",
          roleAdmin: "Admin",
          roleUser: "User"
        };
  const isLoginPage = pathname === "/login";

  const navItems = [
    { href: "/runs", label: text.runs },
    { href: "/leaderboard", label: text.leaderboard },
    { href: "/runs/new", label: text.newRun }
  ];

  function navClassName(href: string): string {
    const active =
      pathname === href ||
      (href === "/runs" && pathname?.startsWith("/runs/") && pathname !== "/runs/new");
    return active ? "btn btn-primary btn-active" : "btn";
  }

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  useEffect(() => {
    setUserMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!userMenuOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!userMenuRef.current?.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    };

    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, [userMenuOpen]);

  const userRoleLabel = user?.role === "admin" ? text.roleAdmin : text.roleUser;

  return (
    <div className="shell">
      <header className="topbar mb-6">
        <div className="topbar-main">
          <div className="topbar-brand flex items-center gap-3">
            <div className="logo-emblem" aria-hidden>
              <span className="logo-halo" />
              <Image alt="TeleRT logo" className="logo-image" priority src={telertLogo} />
            </div>
            <div>
              <h1 className="title-gradient font-headline text-2xl font-semibold md:text-3xl">{text.title}</h1>
              <p className="brand-subtitle">{text.subtitle}</p>
            </div>
          </div>

          <div className="topbar-utility">
            <div aria-label="Language Switcher" className="topbar-locale-corner" role="group">
              {languageOptions.map((option) => (
                <button
                  className={locale === option.value ? "locale-chip locale-chip-active" : "locale-chip"}
                  key={option.value}
                  onClick={() => setLocale(option.value)}
                  aria-label={`Switch language to ${option.label}`}
                  aria-pressed={locale === option.value}
                  type="button"
                >
                  {option.label}
                </button>
              ))}
            </div>

            {!isLoginPage ? (
              user ? (
                <div className="topbar-user-menu" ref={userMenuRef}>
                  <button
                    aria-expanded={userMenuOpen}
                    aria-haspopup="menu"
                    aria-label={text.accountMenu}
                    className={userMenuOpen ? "topbar-user-trigger topbar-user-trigger-active" : "topbar-user-trigger"}
                    onClick={() => setUserMenuOpen((prev) => !prev)}
                    type="button"
                  >
                    <span className="topbar-user-avatar" aria-hidden>
                      {user.username.slice(0, 1).toUpperCase()}
                    </span>
                    <span className="topbar-user-trigger-copy">
                      <span className="topbar-user-name">{user.username}</span>
                      <span className="topbar-user-role">{userRoleLabel}</span>
                    </span>
                    <span className="topbar-user-caret" aria-hidden>
                      ▾
                    </span>
                  </button>

                  {userMenuOpen ? (
                    <div className="topbar-user-panel" role="menu">
                      <div className="topbar-user-panel-meta">
                        <div className="font-semibold">{user.username}</div>
                        <div className="text-xs uppercase tracking-[0.18em] text-slate-400">{userRoleLabel}</div>
                      </div>
                      <button className="btn topbar-user-panel-action" onClick={() => void handleLogout()} type="button">
                        {isReady ? text.logout : text.signingOut}
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : (
                <Link className="btn" href="/login">
                  {text.login}
                </Link>
              )
            ) : null}
          </div>
        </div>

        {!isLoginPage ? (
          <div className="topbar-actions">
            <nav aria-label="Primary" className="topbar-nav">
              {navItems.map((item) => (
                <Link className={navClassName(item.href)} href={item.href} key={item.href}>
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        ) : null}
      </header>
      {children}
    </div>
  );
}
