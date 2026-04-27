import type { Metadata } from "next";
import { AppShell } from "@/components/common/AppShell";
import { AuthProvider } from "@/components/common/AuthProvider";
import { LocaleProvider } from "@/components/common/LocaleProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "灵弈 TeleRT | 大模型红队安全测评靶场",
  description: "TeleRT 大模型红队安全测评靶场 / TeleRT LLM red team evaluation console"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <LocaleProvider>
          <AuthProvider>
            <AppShell>{children}</AppShell>
          </AuthProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
