"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function ProfilesRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/settings");
  }, [router]);

  return (
    <main className="card mx-auto mt-10 max-w-xl p-6 text-sm text-muted">
      Opening family settings...
    </main>
  );
}
