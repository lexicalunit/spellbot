import {
  combineReducers,
  configureStore,
  createAsyncThunk,
  createSlice,
  MiddlewareArray,
} from "@reduxjs/toolkit"
import SpellAPIClient, { Guild, GuildResponse } from "clients/spellapi"
import { useDispatch } from "react-redux"
import reduxThunk from "redux-thunk"
import { getCookie, removeCookie, setCookie } from "tools"

// Actions
export type BakendLoginArgs = {
  discordToken: string
}

export const backendLogin = createAsyncThunk(
  "backendLogin",
  async (args: BakendLoginArgs, thunk) => {
    const { discordToken } = args
    const client = new SpellAPIClient(discordToken)
    try {
      return (await client.login()).data
    } catch (err) {
      return thunk.rejectWithValue(err.response.status)
    }
  }
)

export type BackendGuildArgs = {
  discordToken: string
  guildId: string
}

export const backendGuild = createAsyncThunk(
  "backendGuild",
  async (args: BackendGuildArgs, thunk) => {
    const { discordToken, guildId } = args
    const client = new SpellAPIClient(discordToken)
    try {
      return (await client.guild(guildId)).data
    } catch (err) {
      return thunk.rejectWithValue(err.response.status)
    }
  }
)

export type BackendLogoutArgs = {
  discordToken: string
}

export const backendLogout = createAsyncThunk(
  "backendLogout",
  async (args: BackendLogoutArgs, thunk) => {
    const { discordToken } = args
    const client = new SpellAPIClient(discordToken)
    try {
      return (await client.logout()).data
    } catch (err) {
      return thunk.rejectWithValue(err.response.status)
    }
  }
)

// Session Slice
export type SessionState = {
  discordToken: string | undefined
  discordUsername: string | undefined
  guilds: Guild[]
  guildDisplay: GuildResponse | undefined
}

const createEmptySessionState = () => {
  return {
    discordToken: undefined,
    discordUsername: undefined,
    guilds: [],
    guildDisplay: undefined,
  }
}

const sessionInitialState = (() => {
  const discordToken = getCookie("discordToken")
  const discordUsername = getCookie("discordUsername")
  const guildsJson = localStorage.getItem("guilds") || undefined
  const guilds = guildsJson ? JSON.parse(guildsJson) : undefined
  const initialState: SessionState = {
    ...createEmptySessionState(),
    discordToken,
    discordUsername,
    guilds,
  }
  return initialState
})()

const removeBrowserState = () => {
  removeCookie("discordToken")
  removeCookie("discordUsername")
  localStorage.removeItem("guilds")
}

const sessionSlice = createSlice({
  name: "session",
  initialState: sessionInitialState,
  reducers: {
    setDiscordToken(state, action) {
      state.discordToken = action.payload
      setCookie("discordToken", state.discordToken)
    },
    clearState(state) {
      Object.assign(state, createEmptySessionState())
      removeBrowserState()
    },
  },
  extraReducers: (builder) => {
    builder.addCase(backendLogin.fulfilled, (state, action) => {
      state.discordUsername = action.payload.username
      setCookie("discordUsername", state.discordUsername)

      state.guilds = action.payload.guilds
      localStorage.setItem("guilds", JSON.stringify(state.guilds))
    })

    builder.addCase(backendGuild.fulfilled, (state, action) => {
      state.guildDisplay = action.payload
    })

    builder.addCase(backendGuild.rejected, (state, action) => {
      if (action.payload === 401) {
        sessionSlice.caseReducers.clearState(state)
      } else {
        state.guildDisplay = undefined
      }
    })
  },
})

// Selectors
export const discordTokenSelector = (state: AppState): string | undefined =>
  state.session.discordToken
export const discordUsernameSelector = (state: AppState): string | undefined =>
  state.session.discordUsername
export const guildsSelector = (state: AppState): Guild[] => state.session.guilds
export const guildSelector = (guildId: string) => {
  return (state: AppState): Guild | undefined => {
    return state.session.guilds.find((guild: Guild) => guild.id === guildId)
  }
}
export const guildDisplaySelector = (
  state: AppState
): GuildResponse | undefined => state.session.guildDisplay
export const loggedInSelector = (state: AppState): boolean => {
  return !!state.session.discordUsername && !!state.session.discordToken
}

// Actions
export const { setDiscordToken, clearState } = sessionSlice.actions

// Dispatch
export type AppDispatch = typeof store.dispatch
export const useAppDispatch = (): AppDispatch => useDispatch<AppDispatch>()

const reducer = combineReducers({ session: sessionSlice.reducer })
const middleware = new MiddlewareArray().concat(reduxThunk)
const store = configureStore({ reducer, middleware })
export type AppState = ReturnType<typeof store.getState>
export default store
