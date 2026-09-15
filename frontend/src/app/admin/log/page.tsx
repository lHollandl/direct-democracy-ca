import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Everything an administrator has done",
};

export default function Page() {
  return <PageClient />;
}
