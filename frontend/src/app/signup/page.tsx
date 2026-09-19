import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Join your community",
};

export default function Page() {
  return <PageClient />;
}
