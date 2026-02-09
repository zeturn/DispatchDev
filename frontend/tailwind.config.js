/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['Fraunces', 'ui-serif', 'Georgia', 'serif'],
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        paper: '#fbfaf7',
        ink: '#26262e',
        muted: '#71707b',
        line: '#e7e3da',
        water: { 50:'#f1f7fb',100:'#e3eef6',200:'#c7dded',300:'#9cc4e0',400:'#6ba6cf',500:'#4589b8',600:'#336f9c',700:'#2a587e',800:'#264c69',900:'#244056' },
        rose: { 50:'#fdf2f3',100:'#fbe4e7',200:'#f6c9d0',300:'#eea3af',400:'#e1778a',500:'#cf566d',600:'#b3415a',700:'#943a4e',800:'#7c3344',900:'#6a2f3d' },
        sage: { 50:'#f3f7f1',100:'#e6efe2',200:'#cfe0c7',300:'#aec9a0',400:'#8aae75',500:'#6c9352',600:'#54763e',700:'#425d33',800:'#374c2c',900:'#2f4027' },
        amber: { 50:'#fdf8ee',100:'#faeccf',200:'#f4d99c',300:'#eebf64',400:'#e3a23a',500:'#cf8521',600:'#b06a18',700:'#905216',800:'#764218',900:'#623819' },
        violet: { 50:'#f6f3fb',100:'#ece4f6',200:'#d8c9ec',300:'#baa3dc',400:'#9a79c9',500:'#7e58b3',600:'#684890',700:'#573c77',800:'#493463',900:'#3f2e56' },
      },
      boxShadow: { DEFAULT:'none', sm:'none', md:'none', lg:'none', xl:'none', '2xl':'none', none:'none' },
      borderRadius: { xl:'0.9rem', '2xl':'1.25rem', '3xl':'1.75rem' },
    },
  },
  plugins: [],
}
