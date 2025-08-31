import Head from "next/head";
import Image from "next/image";
import { Inter } from "next/font/google";
import { redirect } from "next/navigation";


const inter = Inter({ subsets: ["latin"] });

export default function Home() {
  redirect("/dev"); // hoặc "/doctors-schedule" nếu bạn đã tạo route mới
}
