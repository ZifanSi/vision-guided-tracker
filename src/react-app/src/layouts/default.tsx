import clsx from "clsx";

import { Navbar } from "@/components/navbar";

export default function DefaultLayout({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className="relative flex flex-col h-screen">
      <Navbar />
      <main className={clsx("flex-grow", className)}>{children}</main>
    </div>
  );
}
