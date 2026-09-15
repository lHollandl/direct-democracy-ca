import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Write down a problem",
};

export default function Page() {
  return <PageClient />;
}
