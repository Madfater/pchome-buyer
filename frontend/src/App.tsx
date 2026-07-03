import CheckoutGrid from './components/CheckoutGrid'
import LogPanel from './components/LogPanel'
import ProductGrid from './components/ProductGrid'
import TopBar from './components/TopBar'

export default function App() {
  return (
    <>
      <TopBar />
      <main>
        <ProductGrid />
        <CheckoutGrid />
        <LogPanel />
      </main>
    </>
  )
}
