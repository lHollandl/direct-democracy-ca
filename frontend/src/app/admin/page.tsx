import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Administrator controls",
};

export default function Page() {
  return <PageClient />;
}
