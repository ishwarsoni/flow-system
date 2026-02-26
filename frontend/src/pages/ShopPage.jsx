import React, { useState, useEffect } from 'react'
import { shopAPI, playerAPI } from '../api'

const RARITY = {
  common:    { color: '#9ca3af', glow: 'rgba(156,163,175,0.15)', label: 'COMMON' },
  uncommon:  { color: '#00ff88', glow: 'rgba(0,255,136,0.12)', label: 'UNCOMMON' },
  rare:      { color: '#00d4ff', glow: 'rgba(0,212,255,0.18)', label: 'RARE' },
  epic:      { color: '#7c3aed', glow: 'rgba(124,58,237,0.18)', label: 'EPIC' },
  legendary: { color: '#ffd700', glow: 'rgba(255,215,0,0.18)', label: 'LEGENDARY' },
  mythic:    { color: '#ff2040', glow: 'rgba(255,32,64,0.18)', label: 'MYTHIC' },
}

export default function ShopPage() {
  const [items, setItems] = useState([])
  const [coins, setCoins] = useState(0)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(null)
  const [toast, setToast] = useState(null)

  useEffect(() => { loadShop() }, [])

  async function loadShop() {
    try {
      setLoading(true)
      const [itemsRes, profileRes] = await Promise.all([shopAPI.getItems(), playerAPI.getProfile()])
      setItems(itemsRes.data)
      setCoins(profileRes.data.coins)
    } catch (err) {
      setToast({ ok: false, msg: 'Failed to load shop' })
    } finally {
      setLoading(false)
    }
  }

  async function handleBuy(item) {
    if (coins < item.coin_value) {
      setToast({ ok: false, msg: 'INSUFFICIENT COINS' })
      setTimeout(() => setToast(null), 2000)
      return
    }
    setActionLoading(item.slug)
    try {
      const res = await shopAPI.buy(item.slug, 1)
      setToast({ ok: true, msg: res.data.message })
      setCoins(res.data.coins_remaining)
    } catch (err) {
      setToast({ ok: false, msg: err.response?.data?.detail || 'Purchase failed' })
    } finally {
      setActionLoading(null)
      setTimeout(() => setToast(null), 3000)
    }
  }

  if (loading) return (
    <div style={s.loadWrap}><div style={s.spinner} /><p style={s.loadText}>[ LOADING SHOP... ]</p></div>
  )

  return (
    <div style={s.page}>
      {toast && (
        <div style={{ ...s.toast, borderColor: toast.ok ? 'rgba(0,255,136,0.4)' : 'rgba(255,32,64,0.4)', background: toast.ok ? 'rgba(0,255,136,0.06)' : 'rgba(255,32,64,0.06)' }}>
          <span style={{ fontFamily: "'Orbitron',monospace", fontSize: 9, color: toast.ok ? '#00ff88' : '#ff2040', letterSpacing: 2 }}>
            {toast.ok ? '[ PURCHASED ]' : '[ ERROR ]'}
          </span>
          <span style={{ fontSize: 12, color: '#b8d8f0' }}>{toast.msg}</span>
        </div>
      )}

      <div style={s.header}>
        <span style={s.pageTag}>[ ITEM SHOP ]</span>
        <div style={s.headerLine} />
        <div style={s.coinsDisplay}>
          <span style={s.coinsLabel}>COINS</span>
          <span style={s.coinsVal}>{coins.toLocaleString()}</span>
        </div>
      </div>

      <div style={s.grid}>
        {items.map(item => {
          const r = RARITY[item.rarity] || RARITY.common
          const canAfford = coins >= item.coin_value
          return (
            <div key={item.id} style={{ ...s.card, borderColor: `${r.color}30`, boxShadow: `0 0 18px ${r.glow}` }}>
              <div style={s.cardTop}>
                <span style={s.itemIcon}>{item.icon || ''}</span>
                <div style={{ ...s.priceTag, borderColor: 'rgba(255,215,0,0.4)', color: canAfford ? '#ffd700' : '#6b7280' }}>
                   {item.coin_value}
                </div>
              </div>
              <div style={{ ...s.itemName, color: r.color }}>{item.name}</div>
              <div style={s.itemDesc}>{item.description}</div>
              <div style={s.cardFooter}>
                <span style={{ ...s.rarityBadge, color: r.color, borderColor: `${r.color}35` }}>{r.label}</span>
                <button
                  onClick={() => handleBuy(item)}
                  disabled={actionLoading === item.slug || !canAfford}
                  style={{
                    ...s.buyBtn,
                    background: canAfford ? 'rgba(255,215,0,0.1)' : 'rgba(107,114,128,0.1)',
                    borderColor: canAfford ? 'rgba(255,215,0,0.5)' : 'rgba(107,114,128,0.3)',
                    color: canAfford ? '#ffd700' : '#6b7280',
                    cursor: canAfford ? 'pointer' : 'not-allowed',
                  }}
                >
                  {actionLoading === item.slug ? '...' : '[ BUY ]'}
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const s = {
  page: { padding: 24, maxWidth: 1200, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 },
  loadWrap: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 18 },
  spinner: { width: 36, height: 36, border: '2px solid rgba(0,212,255,0.1)', borderTop: '2px solid #00d4ff', borderRadius: '50%', animation: 'spin 1s linear infinite' },
  loadText: { fontFamily: "'Orbitron',monospace", fontSize: 11, color: 'rgba(0,212,255,0.4)', letterSpacing: 3 },
  toast: { padding: '10px 18px', border: '1px solid', borderRadius: 2, display: 'flex', gap: 14, alignItems: 'center' },
  header: { display: 'flex', alignItems: 'center', gap: 16 },
  pageTag: { fontFamily: "'Orbitron',monospace", fontSize: 11, color: 'rgba(0,212,255,0.5)', letterSpacing: 4, whiteSpace: 'nowrap' },
  headerLine: { flex: 1, height: 1, background: 'linear-gradient(90deg,rgba(0,212,255,0.3),transparent)' },
  coinsDisplay: { display: 'flex', alignItems: 'center', gap: 8, padding: '7px 14px', border: '1px solid rgba(255,215,0,0.3)', background: 'rgba(255,215,0,0.05)' },
  coinsLabel: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(255,215,0,0.5)', letterSpacing: 2 },
  coinsVal: { fontFamily: "'Orbitron',monospace", fontSize: 15, fontWeight: 800, color: '#ffd700' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: 14 },
  card: { padding: 16, background: 'rgba(4,12,30,0.9)', border: '1px solid', borderRadius: 2, display: 'flex', flexDirection: 'column', gap: 10, transition: 'all 0.2s' },
  cardTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  itemIcon: { fontSize: 26 },
  priceTag: { fontFamily: "'Orbitron',monospace", fontSize: 11, fontWeight: 700, padding: '2px 10px', border: '1px solid', background: 'rgba(0,0,0,0.4)' },
  itemName: { fontFamily: "'Orbitron',monospace", fontSize: 11, fontWeight: 700, letterSpacing: 1, lineHeight: 1.3 },
  itemDesc: { fontSize: 11, color: '#7a9bb8', lineHeight: 1.5, flex: 1 },
  cardFooter: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 8, borderTop: '1px solid rgba(0,212,255,0.06)', marginTop: 'auto' },
  rarityBadge: { fontFamily: "'Orbitron',monospace", fontSize: 8, padding: '2px 6px', border: '1px solid', letterSpacing: 1 },
  buyBtn: { padding: '5px 12px', border: '1px solid', fontFamily: "'Orbitron',monospace", fontSize: 9, letterSpacing: 1 },
}
