mapboxgl.accessToken = 'pk.eyJ1IjoiY21vcmVub3N0b2tvZSIsImEiOiJjazg5MGZ4OHYwMXA5M25wazBtZXA2dGxwIn0.-6W7ECy-ha5nIUXZ-1o8mg';
const map = new mapboxgl.Map({
    container: 'map',
    style: 'mapbox://styles/mapbox/light-v10', // style: 'mapbox://styles/cmorenostokoe/ck8isca7j0zsk1iqx4k4khk4u'
    center: [-3.479368, 52.455248], //Mid-Wales ish
    zoom: 7
});

let visibleLayers = []
let nickNames = {}

map.on('load', function () {

    // Add Source
    for (const layer of layers) {
        map.addSource(layer.layerSpec.id, {
            'type': 'geojson',
            'data': layer.ref,
        });
    }

    // Add Layers
    for (const layer of layers) {
        const visibility = layer.shownByDefault ? 'visible' : 'none';
        map.addLayer(layer.layerSpec);
        map.setLayoutProperty(layer.layerSpec.id, 'visibility', visibility);
        if (visibility === 'visible') {
            visibleLayers.push(layer.layerSpec.id)
        }
        nickNames[layer.layerSpec.id] = layer.name
    }

    map.fitBounds([
        [-5.7395, 51.2403],
        [-1.6619, 53.6833]
    ]);
});


// Dynamically generate sidebar menu & integrated legend
let categoriesProcessed = []
let subheadings = {}
let orders = {}

for (const layer of layers) {
    // console.log(layer.name)
    const id = layer.layerSpec.id;
    const name = layer.name;
    const checked = layer.shownByDefault;
    const category = layer.category;
    const displayOrder = layer.displayOrder;
    const colorsReversed = layer.colorsReversed;
    const layerType = layer.layerSpec.type;
    const catid = layer.catid;

    let container = document.createElement('div');
    let checkbox = document.createElement('input');
    let label = document.createElement('label');

    checkbox.type = 'checkbox';
    checkbox.value = id;
    checkbox.id = id;
    checkbox.checked = checked;
    checkbox.setAttribute('class', 'checkbox')

    label.setAttribute('for', id);
    // label.setAttribute('class', 'dense');

    if (colorsReversed === true) {
        label.textContent = name.concat('*')
    } else {
        label.textContent = name
    }
    // checkbox.addEventListener('change', checkboxChange);

    container.appendChild(checkbox);
    container.appendChild(label);

    //add item to legend for each category
    if (categoriesProcessed.includes(category)) {
        subheadings[category].push(container)
    } else {
        subheadings[category] = []
        subheadings[category].push(container)
        //Build headings & legends for categories
        if (layerType !== 'circle') {
            let subhead = document.createElement('div');
            subhead.innerHTML = '<h3 class="' + catid + '">' + category + '</h3>';
            subhead.className = 'menu-subhead';
            subhead.setAttribute('class', 'category group');
            subhead.id = category

            let cat_container = document.createElement('div');
            cat_container.setAttribute('class', 'cat_container');

            let colorbar = document.createElement('div');
            //get color stops
            for (const color_stop of layer.layerSpec.paint['fill-color'].stops) {
                let key = document.createElement('div');
                key.className = 'legend-key';
                key.style.backgroundColor = color_stop[1];
                if (colorsReversed === true) {
                    colorbar.insertBefore(key, colorbar.childNodes[0]);
                } else {
                    colorbar.appendChild(key);
                }
            }
            cat_container.append(colorbar);

            // append key and subheading
            subhead.append(cat_container);
            subheadings[category].unshift(subhead);
        }
        categoriesProcessed.push(category);
        orders[category] = displayOrder
    }
}

categoriesOrdered = []
//Order categories and append to menu
for (const o of categoriesProcessed) {
    categoriesOrdered.push([orders[o], o])
}
categoriesOrdered.sort()

for (const cat of categoriesOrdered) {
    const category = cat[1];
    const category_acc = subheadings[category][0];
    const subhead = $(category_acc).children('div.cat_container');
    for (const div of subheadings[category].slice(1)) {
        subhead.append($(div));
    }
    $('#accordion').append(category_acc);
}

function checkboxChange(evt) {
    let id = evt.target.value;
    let visibility = evt.target.checked ? 'visible' : 'none';

    map.setLayoutProperty(id, 'visibility', visibility);

    if (visibleLayers.includes(id)) {
        const index = visibleLayers.indexOf(id);
        if (index > -1) {
            visibleLayers.splice(id, 1);
        }
    } else {
        visibleLayers.push(id);
    }
}

// Mouse - over data pop up
map.on('mousemove', function (e) {

    let defaultTag = "<p>Hover over an area for values</p>";
    // Erase content of InnerHTML to avoid inconstistency when zooming in/out.
    document.getElementById('pd').innerHTML = '';

    let features = map.queryRenderedFeatures(e.point, {
        layers: visibleLayers
    });

    //console.log(layers)

    if (features.length > 0) {
        let areaName, name, nickName, areaValue;
        // Reducer function to concatenate visible layers info
        const reducer = (tag, paragraph) => tag + paragraph;

        if (features[0].properties.hasOwnProperty('lad18nm')) {
            areaName = features[0].properties.lad18nm
        } else if (features[0].properties.hasOwnProperty('areaID')) {
            areaName = features[0].properties.areaID
        } else if (features[0].properties.hasOwnProperty('LSOA11NM')) {
            areaName = features[0].properties.LSOA11NM
        } else {
            areaName = '';
        }

        let htmlText = '<div class="pd_p"><h3><strong>' + areaName + '</strong></h3>';
        let htmlParagraphs = features.reverse().map(function (feature) {
            name = feature.layer.id
            nickName = nickNames[name]
            areaValue = feature.properties[name]
            if (areaValue === undefined)  // this may happen when we have only Community Support Group Visible
                return "";
            if (areaValue == 0) {
                areaValue = areaValue
            } 
            else if (areaValue < 0.001) {
                areaValue = areaValue.toFixed(4)
            } else if (areaValue < 1) {
                areaValue = areaValue.toFixed(2)
            } else if (areaValue.countDecimals() > 4) {
                areaValue = areaValue.toFixed(1)
            }
            return "<p>" + nickName + ": <strong>" + areaValue + "</strong></p>";
        });
        htmlText += htmlParagraphs.reduce(reducer);
        htmlText += "</div>";
        document.getElementById('pd').innerHTML = htmlText
        //document.getElementById('pd').innerHTML = '<h3><strong>' + areaName + '</strong></h3><p><strong><em>' + (areaValue*divisor).toFixed(2) + '</strong> groups per '  + divisor + ' people </em></p>';
    } else {
        document.getElementById('pd').innerHTML = defaultTag;
    }
});

Number.prototype.countDecimals = function () {
    if (Math.floor(this.valueOf()) === this.valueOf()) return 0;
    return this.toString().split(".")[1].length || 0;
}

// Sidebar opener and closer
const sdbr = d3.select("div.sidebar");
const bdy = d3.select("body");
const open_close = bdy.append("svg").attr("id", "open_close");
open_close.append("circle").attr("id", "opener").attr("cx", 20).attr("cy", 20).attr("r", 20).attr("fill", "#fff").attr("opacity", 0.5);
let sidebar_open = true;
const cross_lines = open_close.append("g").attr("class", "cross_lines");
cross_lines.append("path").attr("d", "M 20 10 V 30").attr("stroke", "#4c4c4c").attr("stroke-width", 4).attr("stroke-linecap", "round");
cross_lines.append("path").attr("d", "M 10 20 H 30").attr("stroke", "#4c4c4c").attr("stroke-width", 4).attr("stroke-linecap", "round");
open_close.style("transform", "rotate(-45deg)");

d3.select("#opener").on("click", _ => {
    if (sidebar_open) {
        sdbr.transition().duration(750).style("right", "-23rem");
        open_close.transition().duration(750).style("transform", "rotate(90deg)");
        sidebar_open = false;
    } else {
        sdbr.transition().duration(750).style("right", "0rem");
        open_close.transition().duration(750).style("transform", "rotate(-45deg)");
        sidebar_open = true;
    }
});

const mq = window.matchMedia("(max-width: 813px)");
if (mq.matches) {
    const b = document.getElementById('opener');
    let evt = new MouseEvent("click");
    b.dispatchEvent(evt);
}