import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Direct Democracy Explained",
};

export default function Page() {
  return <PageClient />;
}
