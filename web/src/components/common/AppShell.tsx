"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import telertLogo from "../../../assets/图片1.png";
import { type Locale } from "@/lib/i18n";
import { useI18n } from "@/components/common/LocaleProvider";

const languageOptions: Array<{ value: Locale; label: string }> = [
  { value: "zh", label: "中文" },
  { value: "en", label: "EN" }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { locale, setLocale } = useI18n();
  const text =
    locale === "zh"
      ? {
          title: "灵弈TeleRT大模型红队安全测评靶场",
          subtitle: "红队流水线控制平面",
          liveTelemetry: "实时遥测",
          aiSafetyOps: "AI 安全运营",
          humanLoop: "人类在环",
          runs: "运行列表",
          leaderboard: "排行榜",
          newRun: "新建任务"
        }
      : {
          title: "Runs Console",
          subtitle: "Red Team Pipeline Control Plane",
          liveTelemetry: "Live Telemetry",
          aiSafetyOps: "AI Safety Ops",
          humanLoop: "Human-in-the-loop",
          runs: "Runs",
          leaderboard: "Leaderboard",
          newRun: "New Run"
        };

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

  return (
    <div className="shell">
      <header className="topbar mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="logo-emblem" aria-hidden>
            <span className="logo-halo" />
            <Image alt="TeleRT logo" className="logo-image" priority src={telertLogo} />
          </div>
          <div>
            <h1 className="title-gradient font-headline text-2xl font-semibold md:text-3xl">{text.title}</h1>
            <p className="brand-subtitle">{text.subtitle}</p>
            <div className="hud-strip mt-2">
              <span className="hud-pill hud-pill-live">
                <span className="refresh-dot" />
                {text.liveTelemetry}
              </span>
              <span className="hud-pill">{text.aiSafetyOps}</span>
              <span className="hud-pill">{text.humanLoop}</span>
            </div>
          </div>
        </div>

        <div className="topbar-actions flex flex-wrap items-center gap-2 text-sm">
          <nav aria-label="Primary" className="topbar-nav flex items-center gap-2">
            {navItems.map((item) => (
              <Link className={navClassName(item.href)} href={item.href} key={item.href}>
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="topbar-locale flex items-center gap-2">
            {languageOptions.map((option) => (
              <button
                className={locale === option.value ? "btn btn-primary" : "btn"}
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
        </div>
      </header>
      {children}
    </div>
  );
}
