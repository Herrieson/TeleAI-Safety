"use client";

import Image from "next/image";
import Link from "next/link";
import telertLogo from "../../../assets/telert-logo.png";
import { type Locale } from "@/lib/i18n";
import { useI18n } from "@/components/common/LocaleProvider";

const languageOptions: Array<{ value: Locale; label: string }> = [
  { value: "zh", label: "中文" },
  { value: "en", label: "EN" }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { locale, setLocale } = useI18n();
  const text =
    locale === "zh"
      ? {
          title: "运行控制台",
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

  return (
    <div className="shell">
      <header className="topbar mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Image alt="TeleRT logo" className="h-10 w-10 rounded-md object-contain" priority src={telertLogo} />
          <div>
            <p className="label mb-1">TeleRT</p>
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

        <div className="flex flex-wrap items-center gap-2 text-sm">
          <nav className="flex items-center gap-2">
            <Link className="btn" href="/runs">
              {text.runs}
            </Link>
            <Link className="btn" href="/leaderboard">
              {text.leaderboard}
            </Link>
            <Link className="btn btn-primary" href="/runs/new">
              {text.newRun}
            </Link>
          </nav>
          <div className="flex items-center gap-2">
            {languageOptions.map((option) => (
              <button
                className={locale === option.value ? "btn btn-primary" : "btn"}
                key={option.value}
                onClick={() => setLocale(option.value)}
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
