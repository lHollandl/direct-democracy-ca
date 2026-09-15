import type { Metadata } from "next";
import PageClient from "./PageClient";

export const metadata: Metadata = {
  title: "Cookies",
};

export default function Page() {
  return <PageClient />;
}
