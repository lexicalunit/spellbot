import Cookies from "js-cookie"

export function getCookie(name: string): string | undefined {
  return Cookies.get(name)
}

export function setCookie(name: string, value: string | undefined): void {
  if (value === undefined) return
  Cookies.set(name, value, {
    expires: 365,
    path: "/",
    sameSite: "strict",
    secure: false,
  })
}

export function removeCookie(name: string): void {
  Cookies.remove(name, { path: "/", sameSite: "strict" })
}
