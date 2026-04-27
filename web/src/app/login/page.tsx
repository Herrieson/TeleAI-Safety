"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/common/AuthProvider";
import { ApiError, login } from "@/lib/api";
import { useI18n } from "@/components/common/LocaleProvider";

export default function LoginPage() {
  const router = useRouter();
  const { locale } = useI18n();
  const { setAuthenticatedUser } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const text =
    locale === "zh"
      ? {
          eyebrow: "访问控制",
          title: "登录 TeleRT",
          description: "仅后台创建的账号可访问平台。登录后将只看到自己创建的运行任务。",
          username: "用户名",
          password: "密码",
          placeholderUsername: "输入用户名",
          placeholderPassword: "输入密码",
          submit: "登录",
          submitting: "登录中...",
          hint: "如需账号，请联系管理员创建。"
        }
      : {
          eyebrow: "Access Control",
          title: "Sign in to TeleRT",
          description: "Only administrator-created accounts can access the console. After sign-in, you will only see your own runs.",
          username: "Username",
          password: "Password",
          placeholderUsername: "Enter username",
          placeholderPassword: "Enter password",
          submit: "Sign In",
          submitting: "Signing in...",
          hint: "Contact an administrator if you need an account."
        };

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const response = await login({
        username,
        password
      });
      setAuthenticatedUser(response.user);
      router.replace("/runs");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : String(err);
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto max-w-xl pt-8 md:pt-16">
      <div className="panel overflow-hidden p-6 md:p-8">
        <div className="mb-6">
          <p className="label mb-3">{text.eyebrow}</p>
          <h2 className="font-headline text-3xl font-semibold text-slate-50">{text.title}</h2>
          <p className="mt-3 max-w-lg text-sm text-slate-300">{text.description}</p>
        </div>

        <form className="space-y-5" onSubmit={(event) => void handleSubmit(event)}>
          <label className="block space-y-2">
            <span className="label">{text.username}</span>
            <input
              autoComplete="username"
              className="input"
              onChange={(event) => setUsername(event.target.value)}
              placeholder={text.placeholderUsername}
              type="text"
              value={username}
            />
          </label>

          <label className="block space-y-2">
            <span className="label">{text.password}</span>
            <input
              autoComplete="current-password"
              className="input"
              onChange={(event) => setPassword(event.target.value)}
              placeholder={text.placeholderPassword}
              type="password"
              value={password}
            />
          </label>

          {error ? <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{error}</div> : null}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-400">{text.hint}</p>
            <button className="btn btn-primary min-w-[132px]" disabled={submitting} type="submit">
              {submitting ? text.submitting : text.submit}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
