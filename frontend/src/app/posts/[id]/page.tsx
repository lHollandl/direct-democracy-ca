import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "A problem report",
};

export default function Page() {
  return <PageClient />;
}
