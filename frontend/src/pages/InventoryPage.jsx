import React, { useState, useEffect } from 'react'
import { inventoryAPI } from '../api'

const RARITY = {
  common:    { color: '#9ca3af', glow: 'rgba(156,163,175,0.2)', label: 'COMMON' },
  uncommon:  { color: '#00ff88', glow: 'rgba(0,255,136,0.15)', label: 'UNCOMMON' },
  rare:      { color: '#00d4ff', glow: 'rgba(0,212,255,0.2)', label: 'RARE' },
  epic:      { color: '#7c3aed', glow: 'rgba(124,58,237,0.2)', label: 'EPIC' },
  legendary: { color: '#ffd700', glow: 'rgba(255,215,0,0.2)', label: 'LEGENDARY' },
  mythic:    { color: '#ff2040', glow: 'rgba(255,32,64,0.2)', label: 'MYTHIC' },
}

export default function InventoryPage() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionLoading, setActionLoading] = useState(null)
  const [toast, setToast] = useState(null)

  useEffect(() => { loadInventory() }, [])

  async function loadInventory() {
    try {
      setLoading(true)
      const res = await inventoryAPI.list()
      setItems(res.data)
    } catch (err) {
      setError('Failed to load inventory')
    } finally {
      setLoading(false)
    }
  }

  async function handleUse(invItem) {
    if (invItem.item.item_type !== 'consumable') return
    setActionLoading(invItem.id)
    try {
      const res = await inventoryAPI.use(invItem.item.id)
      setToast({ ok: true, msg: res.data.message })
      await loadInventory()
    } catch (err) {
      setToast({ ok: false, msg: err.response?.data?.detail || 'Failed to use item' })
    } finally {
      setActionLoading(null)
      setTimeout(() => setToast(null), 3000)
    }
  }

  if (loading) return (
    <div style={s.loadWrap}><div style={s.spinner} /><p style={s.loadText}>[ LOADING INVENTORY... ]</p></div>
  )

  return (
    <div style={s.page}>
      {toast && (
        <div style={{ ...s.toast, borderColor: toast.ok ? 'rgba(0,255,136,0.4)' : 'rgba(255,32,64,0.4)', background: toast.ok ? 'rgba(0,255,136,0.06)' : 'rgba(255,32,64,0.06)' }}>
          <span style={{ fontFamily: "'Orbitron',monospace", fontSize: 9, color: toast.ok ? '#00ff88' : '#ff2040', letterSpacing: 2 }}>
            {toast.ok ? '[ ITEM USED ]' : '[ ERROR ]'}
          </span>
          <span style={{ fontSize: 12, color: '#b8d8f0' }}>{toast.msg}</span>
        </div>
      )}

      <div style={s.header}>
        <span style={s.pageTag}>[ INVENTORY ]</span>
        <div style={s.headerLine} />
        <span style={s.itemCount}>{items.length} ITEMS</span>
      </div>

      {error && <div style={s.errBox}>{error}</div>}

      {items.length === 0 ? (
        <div style={s.empty}>
          <div style={s.emptyIcon}></div>
          <p style={s.emptyText}>[ INVENTORY EMPTY ]</p>
          <p style={s.emptyHint}>COMPLETE QUESTS TO EARN ITEMS</p>
        </div>
      ) : (
        <div style={s.grid}>
          {items.map(invItem => {
            const item = invItem.item
            const r = RARITY[item.rarity] || RARITY.common
            const isConsumable = item.item_type === 'consumable'
            return (
              <div key={invItem.id} style={{ ...s.card, borderColor: `${r.color}35`, boxShadow: `0 0 20px ${r.glow}` }}>
                <div style={s.cardTop}>
                  <span style={s.itemIcon}>{item.icon || ''}</span>
                  <span style={{ ...s.qtyBadge, borderColor: `${r.color}50`, color: r.color }}>x{invItem.quantity}</span>
                </div>
                <div style={{ ...s.itemName, color: r.color }}>{item.name}</div>
                <div style={s.itemDesc}>{item.description}</div>
                <div style={s.cardFooter}>
                  <span style={{ ...s.rarityBadge, color: r.color, borderColor: `${r.color}40` }}>{r.label}</span>
                  {isConsumable && (
                    <button
                      onClick={() => handleUse(invItem)}
                      disabled={actionLoading === invItem.id}
                      style={{ ...s.useBtn, background: `${r.color}18`, borderColor: `${r.color}50`, color: r.color }}
                    >
                      {actionLoading === invItem.id ? '...' : '[ USE ]'}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
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
  itemCount: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.35)', letterSpacing: 2, whiteSpace: 'nowrap' },
  errBox: { padding: '10px 16px', background: 'rgba(255,32,64,0.08)', border: '1px solid rgba(255,32,64,0.25)', color: '#ff6070', fontSize: 13 },
  empty: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '80px 0' },
  emptyIcon: { fontSize: 40, color: 'rgba(0,212,255,0.2)' },
  emptyText: { fontFamily: "'Orbitron',monospace", fontSize: 13, color: 'rgba(0,212,255,0.3)', letterSpacing: 4 },
  emptyHint: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.2)', letterSpacing: 2 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(190px,1fr))', gap: 14 },
  card: { padding: 16, background: 'rgba(4,12,30,0.9)', border: '1px solid', borderRadius: 2, display: 'flex', flexDirection: 'column', gap: 10, transition: 'all 0.2s' },
  cardTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  itemIcon: { fontSize: 26 },
  qtyBadge: { fontFamily: "'Orbitron',monospace", fontSize: 10, fontWeight: 700, padding: '2px 8px', border: '1px solid', background: 'rgba(0,0,0,0.4)' },
  itemName: { fontFamily: "'Orbitron',monospace", fontSize: 11, fontWeight: 700, letterSpacing: 1, lineHeight: 1.3 },
  itemDesc: { fontSize: 11, color: '#7a9bb8', lineHeight: 1.5, flex: 1 },
  cardFooter: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 8, borderTop: '1px solid rgba(0,212,255,0.07)', marginTop: 'auto' },
  rarityBadge: { fontFamily: "'Orbitron',monospace", fontSize: 8, padding: '2px 6px', border: '1px solid', letterSpacing: 1 },
  useBtn: { padding: '4px 10px', border: '1px solid', fontFamily: "'Orbitron',monospace", fontSize: 9, cursor: 'pointer', letterSpacing: 1 },
}
