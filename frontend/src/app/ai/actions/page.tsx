import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Everything AI has done here",
};

export default function Page() {
  return <PageClient />;
}
