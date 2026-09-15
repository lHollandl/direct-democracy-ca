import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "What people are working on",
};

export default function Page() {
  return <PageClient />;
}
