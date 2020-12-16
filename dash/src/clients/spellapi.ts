import axios, { AxiosResponse } from "axios"

export type Guild = {
  id: string
  name: string
}

export type LoginResponse = {
  username: string
  guilds: Guild[]
}

class SpellAPIClient {
  discordAccessToken: string

  config: {
    headers: { accept: string }
  }

  constructor(discordAccessToken: string) {
    this.discordAccessToken = discordAccessToken
    this.config = { headers: { accept: "application/json" } }
  }

  async login(): Promise<AxiosResponse<LoginResponse>> {
    const endpoint = "/api/login"
    const body = { discord_access_token: this.discordAccessToken }
    return axios.post(endpoint, body, this.config)
  }

  async test(): Promise<AxiosResponse> {
    return axios.get("/api/test", this.config)
  }
}

export default SpellAPIClient
