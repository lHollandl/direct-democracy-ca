import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Every published fingerprint",
};

export default function Page() {
  return <PageClient />;
}
