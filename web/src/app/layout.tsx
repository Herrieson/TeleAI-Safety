import type { Metadata } from "next";
import { AppShell } from "@/components/common/AppShell";
import { LocaleProvider } from "@/components/common/LocaleProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "TeleRT 运行控制台 | Runs Console",
  description: "TeleRT 红队流水线控制台 / TeleRT red team pipeline web console"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <LocaleProvider>
          <AppShell>{children}</AppShell>
        </LocaleProvider>
      </body>
    </html>
  );
}
