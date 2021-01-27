import axios, { AxiosResponse } from "axios"

export type Guild = {
  id: string
  name: string
}

export type LoginResponse = {
  username: string
  guilds: Guild[]
}

export type GuildResponse = {
  serverPrefix: string
  expireTimeMinutes: string
  privateLinks: boolean
  showSpectateLink: boolean
  motdVisibilty: string
  powerEnabled: boolean
  tagsEnabled: boolean
  voiceEnabled: boolean
  serverMotd: string
  gamesPlayed: number
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

  async guild(guildId: string): Promise<AxiosResponse<GuildResponse>> {
    return axios.get(`/api/guild/${guildId}`, this.config)
  }

  async logout(): Promise<AxiosResponse> {
    const endpoint = "/api/logout"
    return axios.post(endpoint, this.config)
  }
}

export default SpellAPIClient
