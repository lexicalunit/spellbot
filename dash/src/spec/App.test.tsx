import { render, screen } from "@testing-library/react"
import App from "components/App"
import React from "react"
import { Provider } from "react-redux"
import { BrowserRouter } from "react-router-dom"
import store from "state"

test("renders learn react link", async () => {
  render(
    <Provider store={store}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </Provider>
  )

  const titleElement = await screen.getByTestId("welcome-title")
  expect(titleElement).toBeInTheDocument()
})
