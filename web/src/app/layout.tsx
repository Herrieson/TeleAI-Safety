import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import telertLogo from "../../assets/telert-logo.png";
import "./globals.css";

export const metadata: Metadata = {
  title: "TeleRT Runs Console",
  description: "Web console for TeleRT pipeline runs"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="topbar mb-6 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Image alt="TeleRT logo" className="h-10 w-10 rounded-md object-contain" priority src={telertLogo} />
              <div>
                <p className="label mb-1">TeleRT</p>
                <h1 className="title-gradient font-headline text-2xl font-semibold md:text-3xl">Runs Console</h1>
                <p className="brand-subtitle">Red Team Pipeline Control Plane</p>
              </div>
            </div>
            <nav className="flex items-center gap-2 text-sm">
              <Link className="btn" href="/runs">
                Runs
              </Link>
              <Link className="btn btn-primary" href="/runs/new">
                New Run
              </Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
